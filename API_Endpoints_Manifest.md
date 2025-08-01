# API Endpoints Manifest

## Overview
This document provides a comprehensive list of all API endpoints in the Chirp application, organized by functional area. Each endpoint includes the HTTP method, route, authentication requirements, and expected input/output parameters.

---

## 1. Authentication & Authorization

### 1.1 User Registration & Login

#### POST `/auth/signup`
**Description:** Register a new seller account
**Authentication:** None
**Input:**
```json
{
  "email": "string",
  "agency_name": "string", 
  "phone": "string",
  "role": "string",
  "name": "string"
}
```
**Output:**
```json
{
  "message": "Seller created successfully",
  "name": "string",
  "user_id": "uuid"
}
```

#### POST `/auth/login`
**Description:** Authenticate user and get access tokens
**Authentication:** None
**Input:**
```json
{
  "email": "string",
  "password": "string"
}
```
**Output:**
```json
{
  "access_token": "string",
  "refresh_token": "string", 
  "user_id": "uuid"
}
```

#### POST `/auth/refresh`
**Description:** Refresh access token using refresh token
**Authentication:** Refresh token required
**Input:** None
**Output:**
```json
{
  "access_token": "string",
  "refresh_token": "string"
}
```

#### POST `/auth/logout`
**Description:** Logout user and invalidate tokens
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "message": "Successfully logged out"
}
```

#### POST `/auth/reset_password`
**Description:** Reset user password with old password validation
**Authentication:** None
**Input:**
```json
{
  "email": "string",
  "old_password": "string",
  "new_password": "string"
}
```
**Output:**
```json
{
  "message": "Password reset successful. A confirmation email has been sent.",
  "user_id": "uuid"
}
```

#### POST `/auth/generate_test_token`
**Description:** Generate a test access token for a user by email (testing purposes only)
**Authentication:** None (protected by secret value)
**Input:**
```json
{
  "secret": "string",
  "email": "string"
}
```
**Output:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "user_id": "uuid",
  "user": {
    "id": "uuid",
    "name": "string",
    "email": "string",
    "phone": "string",
    "role": "string",
    "agency_id": "uuid"
  }
}
```

### 1.2 Google OAuth Integration

#### GET `/google_auth/login`
**Description:** Redirect to Google OAuth login
**Authentication:** JWT required
**Input:** None
**Output:** Redirect to Google OAuth

#### GET `/google_auth/callback`
**Description:** Handle Google OAuth callback
**Authentication:** None
**Input:** OAuth callback parameters
**Output:**
```json
{
  "message": "Google connected successfully!"
}
```

#### GET `/google_auth/calendar`
**Description:** Get Google Calendar events
**Authentication:** JWT required
**Input:** None
**Output:** Google Calendar events data

#### GET `/google_auth/logout`
**Description:** Disconnect Google account
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "message": "Google disconnected successfully!"
}
```

---

## 2. User Management

### 2.1 User Profile & Team Management

#### GET `/user/get_user`
**Description:** Get current user profile information
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string", 
  "phone": "string",
  "role": "string",
  "last_week_performance_analysis": "string",
  "name": "string"
}
```



#### POST `/user/set_manager`
**Description:** Assign a manager to a user
**Authentication:** None
**Input:**
```json
{
  "user_email": "string",
  "manager_email": "string"
}
```
**Output:**
```json
{
  "message": "Manager assigned successfully"
}
```

---

## 3. Meeting & Call Management

### 3.1 Meeting Operations

#### GET `/meetings/get_next/<user_id>`
**Description:** Get upcoming meetings for a user
**Authentication:** None
**Input:** 
- Path: `user_id` (string)
- Query: `num_events` (optional, integer)
**Output:**
```json
[]
```

#### POST `/meetings/create`
**Description:** Create a new meeting
**Authentication:** None
**Input:** Not implemented
**Output:**
```json
{
  "error": "Not implemented"
}
```

#### GET `/meetings/call_history`
**Description:** Get call history for user or team members
**Authentication:** JWT required
**Input:**
- Query: `team_member_ids` (optional, array of UUIDs)
- Query: `time_frame` (optional, string, default: "today") - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:** Call history data
```json
[
  {
    "id": "string",
    "title": "string",
    "source": "string",  // "phone" or "google_meets"
    "start_time": "ISO datetime",
    "end_time": "ISO datetime",
    "buyer_number": "string",
    "buyer_name": "string",
    "buyer_email": "string",
    "seller_number": "string",
    "analysis_status": "string",  // "Processing", "Completed", "Not Recorded", "Missed", "Rejected"
    "duration": "string",
    "call_notes": "string",
    "user_name": "string",
    "user_email": "string",
    "call_direction": "string",  // "incoming", "outgoing"
    "call_type": "string",
    "app_call_type": "string",
    "call_summary": "string"
  }
]
```

#### GET `/meetings/call_data/<meeting_id>`
**Description:** Get detailed meeting data by ID including call performance metrics
**Authentication:** JWT required
**Input:**
- Path: `meeting_id` (UUID)
- Query: `team_member_id` (optional, UUID)
**Output:**
```json
{
  "id": "uuid",
  "mobile_app_call_id": "string",
  "buyer_id": "uuid",
  "seller_id": "uuid",
  "source": "string",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime",
  "transcription": "string",
  "direction": "string",
  "title": "string",
  "call_purpose": "string",
  "key_discussion_points": "object",
  "buyer_pain_points": "object",
  "solutions_discussed": "object",
  "risks": "object",
  "summary": "object",
  "type": "object",
  "job": {
    "id": "uuid",
    "status": "string",
    "start_time": "ISO datetime",
    "end_time": "ISO datetime"
  },
  "call_performance": {
    "overall_score": 7.5,
    "analyzed_at": "ISO datetime",
    "metrics": {
      "intro": {
        "score": 8.5,
        "date": "2024-01-15",
        "reason": "Excellent value proposition"
      },
      "rapport_building": {
        "score": 7.2,
        "date": "2024-01-15",
        "reason": "Good connection established"
      },
      "need_realization": {
        "score": 6.8,
        "date": "2024-01-15",
        "reason": "Identified key pain points"
      },
      "script_adherance": {
        "score": 8.0,
        "date": "2024-01-15",
        "reason": "Followed script well"
      },
      "objection_handling": {
        "score": 7.5,
        "date": "2024-01-15",
        "reason": "Handled objections effectively"
      },
      "pricing_and_negotiation": {
        "score": 6.5,
        "date": "2024-01-15",
        "reason": "Room for improvement"
      },
      "closure_and_next_steps": {
        "score": 8.2,
        "date": "2024-01-15",
        "reason": "Clear next steps defined"
      },
      "conversation_structure_and_flow": {
        "score": 7.8,
        "date": "2024-01-15",
        "reason": "Good flow maintained"
      }
    }
  }
}
```
**Note:** The `call_performance` field will be `null` if no performance analysis has been performed for the meeting.

#### GET `/meetings/call_data/feedback/<meeting_id>`
**Description:** Get meeting feedback
**Authentication:** JWT required
**Input:**
- Path: `meeting_id` (UUID)
**Output:**
```json
{
  "id": "uuid",
  "feedback": "string"
}
```

#### GET `/meetings/call_data/transcription/<meeting_id>`
**Description:** Get meeting transcription
**Authentication:** JWT required
**Input:**
- Path: `meeting_id` (UUID)
**Output:**
```json
{
  "id": "uuid",
  "transcription": "string"
}
```

#### GET `/meetings/last_synced_call`
**Description:** Get last synced call ID for a seller
**Authentication:** None
**Input:**
- Query: `sellerNumber` (string)
**Output:**
```json
{
  "source": "string",
  "last_synced_call_id": "string"
}
```

#### GET `/meetings/last_synced_call_timestamp`
**Description:** Get last synced call timestamp for a seller
**Authentication:** None
**Input:**
- Query: `sellerNumber` (string)
**Output:**
```json
{
  "source": "string",
  "last_synced_call_timestamp": "ISO datetime string"
}
```

#### PUT `/meetings/call_data/summary/<meeting_id>`
**Description:** Update meeting summary
**Authentication:** None
**Input:**
- Path: `meeting_id` (UUID)
- Body:
```json
{
  "callSummary": "string"
}
```
**Output:**
```json
{
  "id": "uuid",
  "summary": "string"
}
```

---

## 4. Call Recording & Processing

### 4.1 Recording Management

#### POST `/call_records/post_recording`
**Description:** Process recording from mobile app
**Authentication:** None
**Input:**
```json
{
  "job_id": "uuid",
  "recording_s3_url": "string"
}
```
**Output:**
```json
{
  "message": "Recording received and ECS speaker diarization task started",
  "job_id": "uuid",
  "recording_s3_url": "string",
  "ecs_task_response": "object"
}
```

#### GET `/call_records/post_exotel_recording`
**Description:** Process Exotel webhook recording
**Authentication:** None
**Input:**
- Query parameters:
  - `CallSid`: string
  - `CallFrom`: string
  - `CallTo`: string
  - `CallStatus`: string
  - `Direction`: string
  - `Created`: string
  - `DialCallDuration`: string
  - `StartTime`: string
  - `EndTime`: string
  - `RecordingUrl`: string
**Output:**
```json
{
  "message": "Exotel call record processed successfully."
}
```

#### POST `/call_records/post_app_call_record`
**Description:** Process mobile app call records
**Authentication:** None
**Input:**
```json
[
  {
    "sellerNumber": "string",
    "appCallId": "string",
    "buyerNumber": "string",
    "callType": "string",  // "incoming", "outgoing", "missed", "rejected"
    "startTime": "string",
    "endTime": "string",
    "duration": "string"
  }
]
```
**Output:**
```json
{
  "message": "Mobile app call records processed successfully."
}
```

**Call Type Status Mapping:**
- `"missed"` → Status: "Missed"
- `"rejected"` → Status: "Rejected" 
- `"incoming"` with duration "0" → Status: "Missed"
- `"outgoing"` with duration "0" → Status: "Not Answered"
- `"incoming"` with duration > 0 → Status: "Processing"
- `"outgoing"` with duration > 0 → Status: "Processing"

### 4.2 Diarization & Analysis

#### POST `/call_recordings/diarization`
**Description:** Retry diarization for a job
**Authentication:** None
**Input:**
```json
{
  "job_id": "uuid"
}
```
**Output:**
```json
{
  "message": "Recording received and ECS speaker diarization task started",
  "job_id": "uuid",
  "ecs_task_response": "object"
}
```

#### POST `/analysis/trigger_analysis`
**Description:** Trigger call analysis for a job
**Authentication:** None
**Input:**
```json
{
  "job_id": "uuid"
}
```
**Output:**
```json
{
  "message": "Analysis task completed successfully for job_id: {job_id}"
}
```

#### POST `/call_recordings/diarization`
**Description:** Retry diarization for a job (alternative to main recording endpoint)
**Authentication:** None
**Input:**
```json
{
  "job_id": "uuid"
}
```
**Output:**
```json
{
  "message": "Recording received and ECS speaker diarization task started",
  "job_id": "uuid",
  "ecs_task_response": "object"
}
```

---

## 5. Buyer Management

### 5.1 Buyer Operations

#### GET `/buyers/all`
**Description:** Get all buyers from the current seller's agency
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "buyers": [
    {
      "id": "uuid",
      "phone": "string",
      "name": "string",
      "email": "string",
      "tags": "array",
      "requirements": "string",
      "solutions_presented": "string",
      "relationship_progression": "string",
      "risks": "string",
      "products_discussed": "string",
      "company_name": "string",
      "last_contacted_at": "ISO datetime",
      "last_contacted_by": "string"
    }
  ],
  "total_count": "number",
  "agency_id": "uuid"
}
```

### 5.2 Buyer Profile Operations

#### GET `/buyers/profile/<buyer_id>`
**Description:** Get buyer profile by ID
**Authentication:** None
**Input:**
- Path: `buyer_id` (UUID)
**Output:**
```json
{
  "id": "uuid",
  "phone": "string",
  "name": "string",
  "email": "string",
  "tags": "array",
  "requirements": "string",
  "solutions_presented": "string",
  "relationship_progression": "string",
  "risks": "string",
  "products_discussed": "string",
  "key_highlights": "object",
  "last_contacted_at": "ISO datetime",
  "last_contacted_by": "string",
  "company_name": "string"
}
```

#### PUT `/buyers/profile/<buyer_id>`
**Description:** Update buyer profile
**Authentication:** None
**Input:**
- Path: `buyer_id` (UUID)
- Body:
```json
{
  "tags": "array",
  "requirements": "string",
  "solutions_presented": "string",
  "relationship_progression": "string",
  "risks": "string",
  "products_discussed": "string",
  "key_highlights": "object"
}
```
**Output:**
```json
{
  "id": "uuid",
  "phone": "string",
  "name": "string",
  "email": "string",
  "tags": "array",
  "requirements": "string",
  "solutions_presented": "string",
  "relationship_progression": "string",
  "risks": "string",
  "products_discussed": "string",
  "key_highlights": "object"
}
```

#### GET `/buyers/call_history/<buyer_id>`
**Description:** Get call history for a buyer
**Authentication:** JWT required
**Input:**
- Path: `buyer_id` (UUID)
**Output:** Call history data

#### GET `/buyers/actions/<buyer_id>`
**Description:** Get all actions for a specific buyer
**Authentication:** JWT required
**Input:**
- Path: `buyer_id` (UUID)
**Output:** Actions data
```json
{
  "buyer_id": "uuid",
  "actions": [
    {
      "id": "uuid",
      "title": "string",
      "due_date": "ISO datetime",
      "status": "string",
      "description": "object",
      "meeting_id": "uuid",
      "meeting_title": "string",
      "meeting_buyer_number": "string",
      "meeting_buyer_name": "string",
      "meeting_seller_name": "string",
      "reasoning": "string",
      "signals": "object",
      "created_at": "ISO datetime",
      "buyer_id": "uuid",
      "buyer_name": "string",
      "buyer_phone": "string",
      "buyer_company_name": "string"
    }
  ],
  "total_count": "number"
}
```

#### GET `/buyers/actions/count/<buyer_id>`
**Description:** Get count of pending actions for a buyer
**Authentication:** JWT required
**Input:**
- Path: `buyer_id` (UUID)
**Output:**
```json
{
  "buyer_id": "uuid",
  "pending_actions_count": "number"
}
```

#### POST `/buyers/create`
**Description:** Create a new buyer
**Authentication:** JWT required
**Input:**
```json
{
  "phone": "string",
  "name": "string",
  "email": "string",
  "company_name": "string",
  "tags": "array",
  "requirements": "string",
  "solutions_presented": "string",
  "relationship_progression": "string",
  "risks": "string", 
  "products_discussed": "string",
  "key_highlights": "object"
}
```
**Output:**
```json
{
  "message": "Buyer created successfully",
  "buyer": {
    "id": "uuid",
    "name": "string",
    "phone": "string",
    "email": "string",
    "company_name": "string",
    "agency_id": "uuid",
    "tags": "array",
    "requirements": "string",
    "solutions_presented": "string",
    "relationship_progression": "string",
    "risks": "string",
    "products_discussed": "string",
    "key_highlights": "object"
  }
}
```

#### GET `/buyers/product_catalogue/<buyer_id>`
**Description:** Get products catalogue for a buyer
**Authentication:** None
**Input:**
- Path: `buyer_id` (UUID)
**Output:**
```json
{
  "id": "uuid",
  "products_discussed": "string"
}
```

---

## 6. Action Management

### 6.1 Action Operations

#### GET `/actions/`
**Description:** Get actions for user or team members with optional status filtering
**Authentication:** JWT required
**Query Parameters:**
- `team_member_ids` (optional): Array of team member UUIDs (managers only)
- `status` (optional): Filter by action status - 'pending' or 'completed'
**Input:** None (parameters in query string)
**Output:** Actions data
```json
{
  "actions": [
    {
      "id": "uuid",
      "title": "string",
      "due_date": "ISO datetime",
      "status": "string",
      "description": "object",
      "meeting_id": "uuid",
      "meeting_title": "string",
      "meeting_buyer_number": "string",
      "meeting_buyer_name": "string",
      "meeting_seller_name": "string",
      "reasoning": "string",
      "signals": "object",
      "created_at": "ISO datetime",
      "buyer_id": "uuid",
      "buyer_name": "string",
      "buyer_phone": "string",
      "buyer_company_name": "string"
    }
  ],
  "total_count": "number",
  "filtered_by_status": "string or null"
}
```

**Sorting Behavior:**
- When `status` parameter is provided: Actions are sorted by creation date (newest first)
- When no `status` parameter: Actions are sorted by due date (earliest first)

#### GET `/actions/<action_id>`
**Description:** Get specific action by ID
**Authentication:** JWT required
**Input:**
- Path: `action_id` (UUID)
**Output:** Action data
```json
{
  "id": "uuid",
  "title": "string",
  "due_date": "ISO datetime",
  "status": "string",
  "description": "object",
  "meeting_id": "uuid",
  "meeting_title": "string",
  "meeting_buyer_number": "string",
  "meeting_buyer_name": "string",
  "meeting_seller_name": "string",
  "reasoning": "string",
  "signals": "object",
  "created_at": "ISO datetime",
  "buyer_id": "uuid",
  "buyer_name": "string",
  "buyer_phone": "string",
  "buyer_company_name": "string"
}
```

#### POST `/actions/update`
**Description:** Bulk update action statuses
**Authentication:** JWT required
**Input:**
```json
[
  {
    "id": "uuid",
    "status": "string"
  }
]
```
**Output:**
```json
{
  "message": "Updated {count} actions successfully"
}
```

---

## 7. Agency Management

### 7.1 Agency Operations

#### GET `/agency/get_agency_names`
**Description:** Get list of available agency names
**Authentication:** None
**Input:** None
**Output:**
```json
{
  "agencies": ["string"]
}
```

#### POST `/agency/create_agency`
**Description:** Create a new agency
**Authentication:** None
**Input:**
```json
{
  "name": "string"
}
```
**Output:**
```json
{
  "message": "Agency created successfully",
  "agency_id": "uuid"
}
```

---

## 8. Health & Monitoring

### 8.1 Health Check

#### GET `/health/hello`
**Description:** Basic health check endpoint
**Authentication:** None
**Input:** None
**Output:**
```json
{
  "message": "Hello, World!"
}
```

---

## 9. Jobs Management

### 9.1 Job Operations

#### GET `/jobs/by_meeting/<meeting_id>`
**Description:** Get job details by meeting ID
**Authentication:** None
**Input:**
- Path: `meeting_id` (UUID)
**Output:**
```json
{
  "job_id": "uuid",
  "meeting_id": "uuid", 
  "status": "string",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime",
  "s3_audio_url": "string"
}
```

#### POST `/jobs/update_status`
**Description:** Update job status (used by external services like analysis pipeline)
**Authentication:** None
**Input:**
```json
{
  "job_id": "uuid",
  "status": "string"
}
```
**Valid Status Values:** `"init"`, `"in_progress"`, `"completed"`, `"failure"`
**Output:**
```json
{
  "message": "Job {job_id} status updated to {status}",
  "job_id": "uuid",
  "status": "string",
  "start_time": "ISO datetime",
  "end_time": "ISO datetime"
}
```

#### GET `/jobs/<job_id>/status`
**Description:** Get current job status
**Authentication:** None
**Input:**
- Path: `job_id` (UUID)
**Output:**
```json
{
  "job_id": "uuid",
  "status": "string",
  "start_time": "ISO datetime", 
  "end_time": "ISO datetime",
  "s3_audio_url": "string"
}
```

#### GET `/jobs/<job_id>/audio_url`
**Description:** Get S3 audio URL for a job
**Authentication:** None
**Input:**
- Path: `job_id` (UUID)
**Output:**
```json
{
  "job_id": "uuid",
  "s3_audio_url": "string"
}
```

#### PUT `/jobs/<job_id>/meeting/transcription`
**Description:** Update meeting transcription for a job (used by transcription services)
**Authentication:** None
**Input:**
- Path: `job_id` (UUID)
- Body:
```json
{
  "transcription": "array or string"
}
```
**Output:**
```json
{
  "message": "Meeting transcription updated for job {job_id}",
  "job_id": "uuid",
  "meeting_id": "uuid",
  "transcription_updated": true
}
```

#### GET `/jobs/<job_id>/context`
**Description:** Get full context for transcription including agency, buyer, seller, and product info (used by enhanced transcription services)
**Authentication:** None
**Input:**
- Path: `job_id` (UUID)
**Output:**
```json
{
  "job_id": "uuid",
  "meeting_id": "uuid",
  "agency_info": {
    "id": "uuid",
    "name": "string",
    "description": "string"
  },
  "buyer_info": {
    "name": "string",
    "phone": "string", 
    "company_name": "string"
  },
  "seller_info": {
    "name": "string",
    "email": "string"
  },
  "product_catalogue": [
    {
      "id": "uuid",
      "name": "string",
      "description": "string",
      "features": "array"
    }
  ]
}
```

---

## 10. Analytics & Reporting

### 10.1 Call Analytics

#### GET `/analytics/total_call_data`
**Description:** Get total call analytics data for the agency with time-based filtering
**Authentication:** JWT required
**Query Parameters:**
- `time_frame` (optional): Time period filter - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month" (default: "today")
**Input:** None (parameters in query string)
**Output:**
```json
{
  "time_frame": "string",
  "start_date": "ISO date",
  "end_date": "ISO date", 
  "granularity": "string",
  "sales_data": {
    "0": {
      "outgoing_calls": "number",
      "incoming_calls": "number",
      "unique_leads": "number"
    }
  },
  "total_outgoing_calls": "number",
  "total_incoming_calls": "number", 
  "total_unique_leads": "number",
  "average_calls_per_seller": "number",
  "top_performers": [
    {
      "seller_name": "string",
      "outgoing_calls": "number"
    }
  ]
}
```

#### GET `/analytics/team_call_data`
**Description:** Get team call analytics with individual seller performance
**Authentication:** JWT required
**Query Parameters:**
- `time_frame` (optional): Time period filter - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month" (default: "today")
**Input:** None (parameters in query string)
**Output:**
```json
{
  "time_frame": "string",
  "start_date": "ISO date",
  "end_date": "ISO date",
  "team_members": [
    {
      "name": "string",
      "email": "string",
      "id": "uuid",
      "phone": "string",
      "total_outgoing_calls": "number",
      "total_incoming_calls": "number",
      "unanswered_outgoing_calls": "number",
      "unique_leads_engaged": "number", 
      "unique_leads_called": "number"
    }
  ],
  "total_outgoing_calls": "number",
  "total_incoming_calls": "number",
  "total_unanswered_outgoing_calls": "number",
  "total_unique_leads_engaged": "number",
  "total_unique_leads_called": "number"
}
```

#### GET `/analytics/call_data/<seller_uuid>`
**Description:** Get detailed call analytics for a specific seller
**Authentication:** JWT required  
**Input:**
- Path: `seller_uuid` (UUID)
- Query: `time_frame` (optional, string, default: "today")
**Output:**
```json
{
  "seller_info": {
    "id": "uuid",
    "name": "string",
    "email": "string"
  },
  "time_frame": "string",
  "call_analytics": {
    "total_calls": "number",
    "outgoing_calls": "number", 
    "incoming_calls": "number",
    "answered_calls": "number",
    "missed_calls": "number",
    "average_call_duration": "number",
    "unique_contacts": "number"
  },
  "performance_trends": "object"
}
```

#### GET `/analytics/seller_call_analytics`
**Description:** Get seller-specific call analytics summary
**Authentication:** JWT required
**Query Parameters:**
- `time_frame` (optional): Time period filter (default: "today")
**Input:** None (parameters in query string)
**Output:**
```json
{
  "seller_analytics": {
    "total_calls_made": "number",
    "calls_answered": "number",
    "calls_missed": "number", 
    "unique_contacts": "number",
    "call_success_rate": "number",
    "average_call_duration": "number"
  },
  "time_frame": "string",
  "period_comparison": "object"
}
```

#### GET `/analytics/seller_call_data/<seller_uuid>`
**Description:** Get comprehensive call data for a specific seller with detailed breakdowns
**Authentication:** JWT required
**Input:**
- Path: `seller_uuid` (UUID)
- Query: `time_frame` (optional, string, default: "today")
**Output:**
```json
{
  "seller_info": {
    "id": "uuid", 
    "name": "string",
    "email": "string",
    "phone": "string"
  },
  "call_summary": {
    "total_calls": "number",
    "outgoing_calls": "number",
    "incoming_calls": "number",
    "call_duration_total": "number",
    "average_call_duration": "number"
  },
  "call_status_breakdown": {
    "answered": "number",
    "missed": "number",
    "rejected": "number",
    "not_answered": "number"
  },
  "time_frame": "string",
  "detailed_calls": "array"
}
```

---

## 11. Extended Agency Management

### 11.1 Product Management

#### POST `/agency/create_product`
**Description:** Create a new product for an agency
**Authentication:** None
**Input:**
```json
{
  "agency_name": "string",
  "name": "string",
  "description": "string",
  "features": "object"
}
```
**Output:**
```json
{
  "message": "Product created successfully",
  "product_id": "uuid",
  "product_name": "string", 
  "agency_id": "uuid",
  "agency_name": "string",
  "description": "string",
  "features": "object"
}
```

#### GET `/agency/product_catalogue`
**Description:** Get product catalogue for an agency
**Authentication:** None
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
**Input:** None (parameters in query string)
**Output:**
```json
{
  "agency": {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "total_products": "number"
  },
  "products": [
    {
      "id": "uuid",
      "name": "string",
      "description": "string",
      "category": "string",
      "features": "array"
    }
  ],
  "categories": "object",
  "generated_at": "ISO datetime",
  "data_source": "string"
}
```

#### PUT `/agency/update_product/<product_id>`
**Description:** Update an existing product
**Authentication:** None
**Input:**
- Path: `product_id` (UUID)
- Body:
```json
{
  "name": "string",
  "description": "string", 
  "features": "object"
}
```
**Output:**
```json
{
  "message": "Product updated successfully",
  "product": {
    "id": "uuid",
    "name": "string",
    "description": "string",
    "features": "object",
    "agency_id": "uuid"
  }
}
```

### 11.2 Agency Information & Management

#### GET `/agency/sellers`
**Description:** Get all sellers for an agency
**Authentication:** None
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
**Input:** None (parameters in query string)
**Output:**
```json
{
  "agency": {
    "id": "uuid",
    "name": "string"
  },
  "sellers": [
    {
      "id": "uuid",
      "name": "string",
      "email": "string",
      "phone": "string",
      "role": "string",
      "created_at": "ISO datetime"
    }
  ],
  "total_sellers": "number"
}
```

#### GET `/agency/details`
**Description:** Get detailed agency information
**Authentication:** None  
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
**Input:** None (parameters in query string)
**Output:**
```json
{
  "agency": {
    "id": "uuid",
    "name": "string", 
    "description": "string",
    "created_at": "ISO datetime"
  },
  "statistics": {
    "total_sellers": "number",
    "total_products": "number",
    "total_buyers": "number"
  }
}
```

#### PUT `/agency/update_description`
**Description:** Update agency description
**Authentication:** None
**Input:**
```json
{
  "agency_id": "uuid",
  "description": "string"
}
```
**Output:**
```json
{
  "message": "Agency description updated successfully",
  "agency": {
    "id": "uuid",
    "name": "string",
    "description": "string"
  }
}
```

#### POST `/agency/add_seller`
**Description:** Add a seller to an agency
**Authentication:** None
**Input:**
```json
{
  "agency_id": "uuid",
  "seller_email": "string"
}
```
**Output:**
```json
{
  "message": "Seller added to agency successfully",
  "seller": {
    "id": "uuid", 
    "email": "string",
    "name": "string"
  },
  "agency": {
    "id": "uuid",
    "name": "string"
  }
}
```

---

## 12. Performance Analytics

### 12.1 Call Performance Metrics

#### POST `/performance/call/<meeting_id>/metrics`
**Description:** Create or update call performance metrics for a specific meeting (used by external analysis services)
**Authentication:** None
**Input:**
```json
{
  "intro": {
    "score": 8.5,
    "date": "2024-01-15", 
    "reason": "Excellent value proposition"
  },
  "rapport_building": {
    "score": 7.2,
    "date": "2024-01-15",
    "reason": "Good connection established"
  },
  "need_realization": {
    "score": 6.8,
    "date": "2024-01-15", 
    "reason": "Identified key pain points"
  },
  "script_adherance": {
    "score": 8.0,
    "date": "2024-01-15",
    "reason": "Followed script well"
  },
  "objection_handling": {
    "score": 7.5,
    "date": "2024-01-15",
    "reason": "Handled objections effectively"
  },
  "pricing_and_negotiation": {
    "score": 6.5,
    "date": "2024-01-15",
    "reason": "Room for improvement"
  },
  "closure_and_next_steps": {
    "score": 8.2,
    "date": "2024-01-15",
    "reason": "Clear next steps defined"
  },
  "conversation_structure_and_flow": {
    "score": 7.8,
    "date": "2024-01-15",
    "reason": "Good flow maintained"
  },
  "overall_score": 7.5,
  "analyzed_at": "2024-01-15T10:30:00Z"
}
```
**Output:**
```json
{
  "message": "Call performance metrics updated successfully",
  "call_performance": {
    "id": "uuid",
    "meeting_id": "uuid", 
    "overall_score": 7.5,
    "analyzed_at": "2024-01-15T10:30:00Z",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

#### GET `/performance/call/<meeting_id>/metrics`
**Description:** Get call performance metrics for a specific meeting
**Authentication:** JWT Required
**Input:** None (meeting_id in URL path)
**Output:**
```json
{
  "message": "Call performance metrics retrieved successfully",
  "performance": {
    "meeting_id": "uuid",
    "overall_score": 7.5,
    "analyzed_at": "2024-01-15T10:30:00Z",
    "metrics": {
      "intro": {
        "score": 8.5,
        "date": "2024-01-15",
        "reason": "Excellent value proposition"
      },
      "rapport_building": {
        "score": 7.2,
        "date": "2024-01-15", 
        "reason": "Good connection established"
      }
      // ... other metrics
    }
  }
}
```

#### DELETE `/performance/call/<meeting_id>/metrics`
**Description:** Delete call performance metrics for a specific meeting (Admin/Manager only)
**Authentication:** JWT Required (Admin/Manager role)
**Input:** None (meeting_id in URL path)
**Output:**
```json
{
  "message": "Call performance metrics deleted successfully"
}
```

#### GET `/performance/user/<user_id>/metrics`
**Description:** Get call performance metrics for a user within a date range with daily averages
**Authentication:** JWT Required
**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format (defaults to 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (defaults to today)
**Input:** None (user_id in URL path, dates in query params)
**Output:**
```json
{
  "message": "User performance metrics retrieved successfully",
  "user_info": {
    "user_id": "uuid",
    "name": "John Doe",
    "email": "john@example.com"
  },
  "date_range": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "daily_metrics": {
    "2024-01-01": {
      "intro": 8.5,
      "rapport_building": 7.2,
      "need_realization": 6.8,
      "script_adherance": 8.0,
      "objection_handling": 7.5,
      "pricing_and_negotiation": 6.5,
      "closure_and_next_steps": 8.2,
      "conversation_structure_and_flow": 7.8,
      "overall_score": 7.5,
      "calls_count": 3
    },
    "2024-01-02": {
      "intro": 7.8,
      "rapport_building": 8.1,
      "overall_score": 7.7,
      "calls_count": 2
    },
    "2024-01-03": null
  },
  "period_summary": {
    "total_calls": 15,
    "days_with_data": 8,
    "days_in_range": 31,
    "overall_averages": {
      "intro": 8.1,
      "rapport_building": 7.6,
      "overall_score": 7.4
    }
  }
}
```

### 12.2 Validation Rules
- All performance scores must be between 0 and 10
- Date format must be YYYY-MM-DD
- Meeting must exist and user must have access
- Only meeting owner, admin, or manager can update metrics
- Only admin or manager can delete metrics
- Users can view their own performance data; admin/manager can view any user's data
- Date range cannot exceed 365 days
- Daily metrics show null for days with no call data

---

## Authentication Types

- **None**: No authentication required
- **JWT**: Requires valid JWT access token in Authorization header
- **Refresh Token**: Requires valid refresh token

## Common Response Formats

### Success Response
```json
{
  "message": "Success message",
  "data": "response data"
}
```

### Error Response
```json
{
  "error": "Error message"
}
```

## HTTP Status Codes

- **200**: Success
- **201**: Created
- **400**: Bad Request
- **401**: Unauthorized
- **404**: Not Found
- **500**: Internal Server Error
- **501**: Not Implemented

---

## Notes

1. All UUIDs are returned as strings in JSON responses
2. Phone numbers are normalized (stored without +) and denormalized (returned with +) automatically
3. Team member access is restricted to users with MANAGER role
4. Some endpoints support bulk operations for efficiency
5. Google OAuth integration requires proper configuration of client credentials
6. File uploads and processing are handled asynchronously via ECS tasks
7. Performance metrics are scored on a 0-10 scale for standardized evaluation
8. Jobs are processed through multiple stages: recording → transcription → analysis → completion
9. External services (transcription, analysis) use dedicated endpoints for status updates and data exchange
10. Analytics endpoints provide comprehensive reporting with flexible time-based filtering 