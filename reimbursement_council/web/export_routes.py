"""The claim export over HTTP (deliverable 2): GET /api/claims/{id}/export.

?download=1 asks the browser to save it as claim-{id}.json. A draft has no export yet (409).
"""

import json
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from reimbursement_council.pipeline.export_claim import export_claim
from reimbursement_council.web.context import WebContext, load_claim
from reimbursement_council.web.demo import WARM_UP_DONE, warming


def add_export_routes(app: FastAPI, ctx: WebContext) -> None:
    @app.get("/api/ready")
    def ready() -> dict[str, bool]:
        """True once the demo warm-up has read every demo file (or no warm-up runs)."""
        return {"ready": WARM_UP_DONE.is_set() or not warming()}

    @app.get("/api/claims/{claim_id}/export")
    def claim_export(claim_id: str, download: int = 0) -> Response:
        claim = load_claim(ctx, claim_id)
        export = export_claim(claim, ctx.store, ctx.reference, ctx.settings, datetime.now(UTC))
        if export is None:
            raise HTTPException(status_code=409, detail="This claim has not been sent yet.")
        body = json.dumps(json.loads(export.model_dump_json()), indent=1, ensure_ascii=False)
        headers = (
            {"Content-Disposition": f'attachment; filename="claim-{claim_id}.json"'}
            if download
            else {}
        )
        return Response(body, media_type="application/json", headers=headers)
