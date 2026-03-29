"""Core pipeline orchestrator — runs the full WebIntel flow.

Flow: Query → Plan → Search → Extract → Verify → Report
Each step pushes SSE events if a session_id is provided.
"""

import uuid
from typing import Optional
from models.report_models import FinalReport
from services import sse_service, supabase_service
from agents import planner, search_agent, extraction_agent, verification_agent, report_agent


async def run_pipeline(
    query: str,
    mode: str,
    query_type: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> FinalReport:
    """Execute the full WebIntel pipeline.
    
    Args:
        query: User's question
        mode: quick | fact_check | research | deep_dive
        query_type: single | compare | track | summarise_url
        session_id: SSE session ID (None for background jobs)
    
    Returns:
        The completed FinalReport
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    step = 0

    async def trace(message: str):
        nonlocal step
        step += 1
        await sse_service.push_trace(session_id, step, message)
        print(f"  [{step}] {message}")

    try:
        # ─── Step 1: Planning ───────────────────────────────
        await trace("Planning query decomposition...")
        plan = await planner.plan_query(query, mode, query_type)
        await trace(f"Generated {len(plan.sub_queries)} sub-queries")

        # ─── Step 2: Parallel Search ────────────────────────
        await trace(f"Dispatching {len(plan.sub_queries)} parallel search agents...")
        search_results = await search_agent.search_parallel(plan.sub_queries)
        await trace(f"Collected {len(search_results)} unique sources")

        if not search_results:
            await sse_service.push_error(session_id, "No search results found. Try a different query.")
            await sse_service.push_done(session_id)
            return FinalReport(
                session_id=session_id,
                query=query,
                query_type=query_type,
                mode=mode,
            )

        # ─── Step 3: Claim Extraction ───────────────────────
        await trace("Extracting structured claims from sources...")
        claims = await extraction_agent.extract_claims(search_results)
        await trace(f"Extracted {len(claims)} atomic claims")

        # ─── Step 4: Verification ───────────────────────────
        await trace("Verifying claims across sources...")
        verified_claims, sources, overall_confidence = await verification_agent.verify_claims(
            claims, mode
        )
        await trace(f"Verified {len(verified_claims)} claims — confidence: {overall_confidence}%")

        # Push individual claim events for live UI
        for vc in verified_claims:
            await sse_service.push_claim(session_id, vc.model_dump())

        # ─── Step 4b: Re-query if needed ────────────────────
        if verification_agent.needs_requery(mode, overall_confidence, verified_claims):
            await trace("Confidence below threshold — triggering re-query...")
            
            # Get weak claims for targeted re-search
            weak_claims = [c for c in verified_claims if c.confidence < 60]
            weak_topics = " ".join(c.claim[:50] for c in weak_claims[:3])
            
            requery_plan = await planner.plan_query(
                f"{query} — focus on verifying: {weak_topics}",
                mode, query_type
            )
            
            await trace(f"Re-searching with {len(requery_plan.sub_queries)} targeted queries...")
            new_results = await search_agent.search_parallel(requery_plan.sub_queries)
            
            if new_results:
                new_claims = await extraction_agent.extract_claims(new_results)
                # Merge new claims with existing
                all_claims = claims + new_claims
                verified_claims, sources, overall_confidence = await verification_agent.verify_claims(
                    all_claims, mode
                )
                await trace(f"Re-verified: {len(verified_claims)} claims — confidence: {overall_confidence}%")

        # ─── Step 5: Report Assembly ────────────────────────
        await trace("Assembling final report...")

        # For track mode, get previous report
        previous_report = None
        if query_type == "track":
            prev = await supabase_service.get_reports(limit=1)
            if prev:
                previous_report = prev[0].get("report")

        report = await report_agent.assemble_report(
            session_id=session_id,
            query=query,
            mode=mode,
            query_type=query_type,
            verified_claims=verified_claims,
            sources=sources,
            overall_confidence=overall_confidence,
            entities=plan.entities if plan.entities else None,
            previous_report=previous_report,
        )

        # ─── Step 6: Save to DB ────────────────────────────
        await trace("Saving report to database...")
        try:
            await supabase_service.save_report(
                session_id=session_id,
                query=query,
                mode=mode,
                query_type=query_type,
                report=report.model_dump(),
                overall_confidence=overall_confidence,
                user_id=user_id,
            )
        except Exception as e:
            print(f"[Pipeline] DB save error (non-fatal): {e}")

        # ─── Push final report + done ───────────────────────
        await sse_service.push_event(session_id, "report", report.model_dump())
        await sse_service.push_done(session_id)

        await trace("Done ✓")
        return report

    except Exception as e:
        error_msg = f"Pipeline error: {str(e)}"
        print(f"[Pipeline] {error_msg}")
        await sse_service.push_error(session_id, error_msg)
        await sse_service.push_done(session_id)
        raise
