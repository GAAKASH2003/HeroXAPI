from fastapi import APIRouter, HTTPException, status, Depends, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List, Dict, Any,Union
import json
import openai
import requests
from fastapi.responses import StreamingResponse
import io
from datetime import datetime
from database import db
from auth import get_current_user
from utils.activity_logger import ActivityLogger
import base64
import mimetypes
from auth import get_current_user
import os
from datetime import datetime
from fastapi.responses import JSONResponse
from typing import List, Optional
import re

router = APIRouter()


class FieldData(BaseModel):
    type: Optional[str] = None
    value: Optional[Union[str, bool, int]] = None  # can be string, bool, or number
    id: Optional[str] = None
    placeholder: Optional[str] = None
    required: Optional[bool] = None  # should be bool, not str

class TrackRequest(BaseModel):
    fields: Dict[str, FieldData]
from fastapi.responses import JSONResponse
from fastapi import status
from datetime import datetime
import json


# ----------- TRACK EMAIL OPEN -----------
@router.get("/f1/{unique_id}")
async def track_user(unique_id: str):
    if not unique_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "unique_id is required"}
        )

    split_array = unique_id.split("*")
    if len(split_array) != 2:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "Invalid unique_id format. Expected <campaign_id>*<user_id>"}
        )

    try:
        campaign_id = int(split_array[0])
        user_id = int(split_array[1])
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "campaign_id and user_id must be integers"}
        )

    campaign = db(
        (db.campaign_results.campaign_id == campaign_id) &
        (db.campaign_results.target_id == user_id)
    ).select().first()

    if not campaign:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": 404, "detail": "Record not found"}
        )

    # Update tracking
    campaign.update_record(
        email_opened=True,
        email_opened_at=campaign.email_opened_at or datetime.utcnow()
    )
    db.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": 200,
            "detail": "Email opened successfully tracked",
            "campaign_id": campaign_id,
            "user_id": user_id,
            "opened_at": str(campaign.email_opened_at)
        }
    )


# ----------- TRACK FORM SUBMISSION -----------
@router.post("/f2/{unique_id}")
async def track_user(unique_id: str, request: Request):
    if not unique_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "unique_id is required"}
        )

    split_array = unique_id.split("*")
    if len(split_array) != 2:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "Invalid unique_id format. Expected <campaign_id>*<user_id>"}
        )

    try:
        campaign_id = int(split_array[0])
        user_id = int(split_array[1])
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "campaign_id and user_id must be integers"}
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "Invalid JSON body"}
        )

    if not isinstance(body, dict):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": 400, "detail": "Body must be a JSON object"}
        )

    campaign_result = db(
        (db.campaign_results.campaign_id == campaign_id) &
        (db.campaign_results.target_id == user_id)
    ).select().first()

    if not campaign_result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"status": 404, "detail": "Record not found"}
        )

    # Prepare updates
    updates = {
        "form_submitted": True,
        "credentials_captured": True
    }
    if campaign_result.form_submitted_at is None:
        updates["form_submitted_at"] = datetime.utcnow().isoformat()  

    try:
        new_data = json.dumps(body)
    except TypeError:
        new_data = str(body)  # fallback to string if body contains non-serializable data

    if campaign_result.captured_data:
        updates["captured_data"] = str(campaign_result.captured_data) + "\n" + new_data
    else:
        updates["captured_data"] = new_data

    # Update DB
    campaign_result.update_record(**updates)
    db.commit()
    json_safe_updates = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in updates.items()}
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": 200,
            "detail": "Form data captured successfully",
            "campaign_id": campaign_id,
            "user_id": user_id,
            "updates": json_safe_updates
        }
    )




# @router.get("/credentials/{campaign_id}/{user_id}")
# async def get_credentials(campaign_id: int, user_id: int, current_user = Depends(get_current_user)):
#     try:
#         if not current_user:
#             return JSONResponse(status_code=403, content={"error": "Not authorized"})

#         campaign_result = db(
#             (db.campaign_results.campaign_id == campaign_id) &
#             (db.campaign_results.target_id == user_id)
#         ).select().first()

#         if not campaign_result:
#             return JSONResponse(status_code=404, content={"error": "Record not found"})

#         raw_data = campaign_result.captured_data
        
#         raw_data_fixed = "[" + raw_data.replace("}\n{", "},{") + "]"

#         parsed_list = json.loads(raw_data_fixed)
        
#         creds_list = []
#         for parsed in parsed_list:
#             fields = parsed.get("fields", {})
#             creds = []
#             for key, field in fields.items():
#                 value = field.get("value")
#                 if value not in [None, "", "null"]:
#                     creds.append(f"{key}: {value}")
#             # creds_list.append(" | ".join(creds))
#             creds_list.append(creds)
        
#         # print({"credentials": creds_list})
#         return {"credentials": creds_list}
    
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})