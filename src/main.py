from fastapi import FastAPI, HTTPException, Query
from mangum import Mangum
import os
import boto3

from models import OptionLevelsResponse
from services.option_service import build_option_levels

# DynamoDB table for cached data
_dynamo = boto3.resource("dynamodb")
_table = _dynamo.Table(os.environ.get("DDB_TABLE_NAME", "OptionLevels"))


app = FastAPI(title="Option Levels API")

@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/api/option-levels", response_model=OptionLevelsResponse)
def get_option_levels(
        ticker: str = Query(..., description="Ticker symbol, e.g. SPY"),
        expiry: str = Query("front", description="Expiry: 'front' for same-day, 'next' for next expiry, or exact YYYY-MM-DD"),
        center: float = Query(None, description="Center price (default = last close)"),
        width: int = Query(20, ge=1, description="Half-range in points"),
        greeks: bool = Query(False, description="Include implied vol & GEX"),
        source: str = Query("live", description="Data source: 'live' or 'cache'"),
        date:   str = Query(None, description="YYYY-MM-DD for cached data")
):

    # Serve cached data if requested
    if source.lower() == "cache":
        if not date:
            raise HTTPException(status_code=400, detail="'date' is required when source=cache")
        key = {"date": date, "ticker_exp": f"{ticker}#{expiry}"}
        resp = _table.get_item(Key=key)
        item = resp.get("Item")
        if not item:
            raise HTTPException(status_code=404, detail="No cached data for given date/expiry")
        return item["payload"]


    result = build_option_levels(
        ticker=ticker,
        expiry_param=expiry,
        center=center,
        width=width,
        include_greeks=greeks
    )

    if not result.get("strikes"):
        raise HTTPException(status_code=404, detail="No strikes in range for given parameters")

    return result

# Lambda handler for API Gateway
api_handler = Mangum(app)