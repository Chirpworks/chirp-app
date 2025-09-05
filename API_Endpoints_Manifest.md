# API Endpoints Manifest

## Overview
This document provides a comprehensive list of all API endpoints in the Chirp application, organized by functional area. Each endpoint includes the HTTP method, route, authentication requirements, and expected input/output parameters.

---

## 1. Authentication & Authorization

### 1.1 User Registration & Login

#### POST `/api/auth/signup`
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

#### POST `/api/auth/login`
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

#### POST `/api/auth/refresh`
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

#### POST `/api/auth/logout`
**Description:** Logout user and invalidate tokens
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "message": "Successfully logged out"
}
```

#### POST `/api/auth/reset_password`
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

#### POST `/api/auth/generate_test_token`
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

#### GET `/api/user/get_user`
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

#### POST `/api/user/set_manager`
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

#### GET `/api/meetings/get_next/<user_id>`
**Description:** Get upcoming meetings for a user
**Authentication:** None
**Input:** 
- Path: `user_id` (string)
- Query: `num_events` (optional, integer)
**Output:**
```json
[]
```

#### POST `/api/meetings/create`
**Description:** Create a new meeting
**Authentication:** None
**Input:** Not implemented
**Output:**
```json
{
  "error": "Not implemented"
}
```

#### GET `/api/meetings/call_history`
**Description:** Get call history for user or team members with pagination support
**Authentication:** JWT required
**Query Parameters:**
- `team_member_ids` (optional, array of UUIDs)
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `page` (optional, integer, default: 1) - Page number (1-based)
- `limit` (optional, integer, default: 50, max: 100) - Number of records per page
- `time_frame` (optional, string, default: "today", **DEPRECATED**)
 - `analysis_status` (optional, string) - When set to `analyzed`, returns only meetings with analysis completed (job status `COMPLETED`)

**Output:** Call history data with pagination metadata
```json
{
  "data": [
    {
      "id": "string",
      "title": "string",
      "source": "string",
      "start_time": "ISO datetime",
      "end_time": "ISO datetime",
      "buyer_number": "string",
      "buyer_name": "string",
      "buyer_email": "string",
      "seller_number": "string",
      "analysis_status": "string",
      "duration": "string",
      "call_notes": "string",
      "user_name": "string",
      "user_email": "string",
      "call_direction": "string",
      "call_type": "string",
      "app_call_type": "string",
      "call_summary": "string"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_count": 500,
    "limit": 50,
    "has_next": true,
    "has_previous": false
  }
}
```

#### GET `/api/meetings/call_data/<uuid:meeting_id>`
**Description:** Get detailed meeting data by ID including call performance metrics
**Authentication:** JWT required
**Query Parameters:**
- `team_member_id` (optional, UUID)
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
      }
    }
  }
}
```

#### GET `/api/meetings/call_data/feedback/<uuid:meeting_id>`
**Description:** Get meeting feedback
**Authentication:** JWT required
**Output:**
```json
{
  "id": "uuid",
  "feedback": "string"
}
```

#### GET `/api/meetings/call_data/transcription/<uuid:meeting_id>`
**Description:** Get meeting transcription
**Authentication:** JWT required
**Output:**
```json
{
  "id": "uuid",
  "transcription": "string"
}
```

#### GET `/api/meetings/last_synced_call_timestamp`
**Description:** Get last synced call timestamp for a seller
**Authentication:** None
**Query Parameters:**
- `sellerNumber` (string)
**Output:**
```json
{
  "source": "string",
  "last_synced_call_timestamp": "ISO datetime string"
}
```

#### PUT `/api/meetings/call_data/summary/<uuid:meeting_id>`
**Description:** Update meeting summary
**Authentication:** None
**Input:**
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

#### POST `/api/call_records/post_recording`
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

#### GET `/api/call_records/post_exotel_recording`
**Description:** Process Exotel webhook recording
**Authentication:** None
**Query Parameters:**
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

#### POST `/api/call_records/post_app_call_record`
**Description:** Process mobile app call records
**Authentication:** None
**Input:**
```json
[
  {
    "sellerNumber": "string",
    "appCallId": "string",
    "buyerNumber": "string",
    "callType": "string",
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

#### POST `/api/call_recordings/diarization`
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

#### POST `/api/analysis/trigger_analysis`
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

---

## 5. Buyer Management

#### GET `/api/buyers/search`
**Description:** Search buyers with fuzzy matching and suggestions
**Authentication:** JWT required
**Query Parameters:**
- `q` (required, string, min: 2 chars) - Search query
- `limit` (optional, integer, default: 20, max: 50) - Maximum number of results
- `suggestion_limit` (optional, integer, default: 5, max: 10) - Maximum number of suggestions
**Rate Limiting:** 10 searches per minute per user
**Output:**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "string",
      "phone": "string", 
      "email": "string",
      "company_name": "string",
      "products_discussed": [
        {
          "product_id": "uuid",
          "product_name": "string",
          "interest_level": "high|medium|low"
        }
      ],
      "last_contacted_at": "ISO datetime",
      "last_contacted_by": "string",
      "match_score": 0.95,
      "match_field": "name|phone|email|company_name"
    }
  ],
  "suggestions": [
    "John Doe",
    "John Smith", 
    "+91 9876543210"
  ],
  "total_count": 45,
  "query": "john",
  "search_time_ms": 150,
  "cached": false,
  "rate_limit": {
    "requests_made": 1,
    "requests_remaining": 9,
    "reset_time": "ISO datetime"
  }
}
```
**Error Responses:**
- `400` - Invalid query (too short, missing, etc.)
- `429` - Rate limit exceeded
- `500` - Search service temporarily unavailable

#### GET `/api/buyers/all`
**Description:** Get all buyers from the current seller's agency with pagination support
**Authentication:** JWT required
**Query Parameters:**
- `page` (optional, integer, default: 1) - Page number (1-based)
- `limit` (optional, integer, default: 50, max: 100) - Number of records per page
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
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_count": 500,
    "limit": 50,
    "has_next": true,
    "has_previous": false
  },
  "agency_id": "uuid"
}
```

#### GET `/api/buyers/profile/<uuid:buyer_id>`
**Description:** Get buyer profile by ID
**Authentication:** None
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
  "products_discussed": [
    {
      "product_name": "string",
      "product_id": "uuid",
      "interest_level": "high|medium|low"
    }
  ],
  "key_highlights": "object",
  "last_contacted_at": "ISO datetime",
  "last_contacted_by": "string",
  "company_name": "string"
}
```

#### PUT `/api/buyers/profile/<uuid:buyer_id>`
**Description:** Update buyer profile
**Authentication:** None
**Input:**
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

#### GET `/api/buyers/call_history/<uuid:buyer_id>`
**Description:** Get call history for a buyer
**Authentication:** JWT required
**Output:** Call history data

#### GET `/api/buyers/actions/<uuid:buyer_id>`
**Description:** Get all actions for a specific buyer
**Authentication:** JWT required
**Output:**
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

#### GET `/api/buyers/actions/count/<uuid:buyer_id>`
**Description:** Get count of pending actions for a buyer
**Authentication:** JWT required
**Output:**
```json
{
  "buyer_id": "uuid",
  "pending_actions_count": "number"
}
```

#### POST `/api/buyers/create`
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

#### GET `/api/buyers/product_catalogue/<uuid:buyer_id>`
**Description:** Get products catalogue for a buyer
**Authentication:** None
**Output:**
```json
{
  "id": "uuid",
  "products_discussed": [
    {
      "product_name": "string",
      "product_id": "uuid",
      "interest_level": "high|medium|low"
    }
  ]
}
```

---

## 6. Action Management

#### GET `/api/actions/`
**Description:** Get actions for user or team members with optional status filtering and pagination support
**Authentication:** JWT required
**Query Parameters:**
- `team_member_ids` (optional): Array of team member UUIDs (managers only)
- `status` (optional): Filter by action status - 'pending' or 'completed'
- `meeting_id` (optional): UUID to fetch actions for a specific meeting
- `page` (optional, integer, default: 1) - Page number (1-based)
- `limit` (optional, integer, default: 50, max: 100) - Number of records per page
**Output:**
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
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_count": 500,
    "limit": 50,
    "has_next": true,
    "has_previous": false
  },
  "filtered_by_status": "string or null",
  "filtered_by_meeting": "string or null"
}
```

#### GET `/api/actions/<uuid:action_id>`
**Description:** Get specific action by ID
**Authentication:** JWT required
**Output:**
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

#### POST `/api/actions/update`
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

#### GET `/api/agency/get_agency_names`
**Description:** Get list of available agency names
**Authentication:** None
**Output:**
```json
{
  "agencies": ["string"]
}
```

#### POST `/api/agency/create_agency`
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

#### POST `/api/agency/create_product`
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

#### GET `/api/agency/product_catalogue`
**Description:** Get product catalogue for an agency
**Authentication:** None
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
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

#### GET `/api/agency/sellers`
**Description:** Get all sellers for an agency
**Authentication:** None
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
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

#### GET `/api/agency/details`
**Description:** Get detailed agency information
**Authentication:** None  
**Query Parameters:**
- `agency_id` (optional): Agency UUID
- `agency_name` (optional): Agency name
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

#### PUT `/api/agency/update_description`
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

#### PUT `/api/agency/update_product/<uuid:product_id>`
**Description:** Update an existing product
**Authentication:** None
**Input:**
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

#### POST `/api/agency/add_seller`
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

## 8. Health & Monitoring

#### GET `/api/health/hello`
**Description:** Basic health check endpoint
**Authentication:** None
**Output:**
```json
{
  "message": "Hello, World!"
}
```

---

## 9. Jobs Management

#### GET `/api/jobs/by_meeting/<uuid:meeting_id>`
**Description:** Get job details by meeting ID
**Authentication:** None
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

#### POST `/api/jobs/update_status`
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

#### GET `/api/jobs/<job_id>/status`
**Description:** Get current job status
**Authentication:** None
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

#### GET `/api/jobs/<job_id>/audio_url`
**Description:** Get S3 audio URL for a job
**Authentication:** None
**Output:**
```json
{
  "job_id": "uuid",
  "s3_audio_url": "string"
}
```

#### PUT `/api/jobs/<job_id>/meeting/transcription`
**Description:** Update meeting transcription for a job (used by transcription services)
**Authentication:** None
**Input:**
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

#### GET `/api/jobs/<job_id>/context`
**Description:** Get full context for transcription including agency, buyer, seller, and product info (used by enhanced transcription services)
**Authentication:** None
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

#### GET `/api/analytics/total_call_data`
**Description:** Get total call analytics data for the agency with time-based filtering
**Authentication:** JWT required
**Query Parameters:**
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `time_frame` (optional, string, **DEPRECATED**) - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:**
```json
{
  "sales_data": {
    "hour0": {
      "outgoing_calls": "number",
      "incoming_calls": "number",
      "unique_leads_engaged": "number"
    }
  },
  "total_data": {
    "total_outgoing_calls": "number",
    "total_incoming_calls": "number", 
    "total_calls": "number",
    "unique_leads_engaged": "number"
  }
}
```

#### GET `/api/analytics/team_call_data`
**Description:** Get team call analytics with individual seller performance
**Authentication:** JWT required
**Query Parameters:**
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `time_frame` (optional, string, **DEPRECATED**) - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:**
```json
{
  "seller_data": [
    {
      "seller_id": "uuid",
      "seller_name": "string",
      "seller_phone": "string",
      "metrics": {
        "total_calls_made": "number",
        "outgoing_calls": "number",
        "incoming_calls": "number",
        "leads_engaged": "number"
      }
    }
  ]
}
```

#### GET `/api/analytics/call_data/<uuid:seller_uuid>`
**Description:** Get detailed call analytics for a specific seller
**Authentication:** JWT required  
**Query Parameters:**
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `time_frame` (optional, string, **DEPRECATED**) - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:**
```json
{
  "outgoing_calls": "number",
  "outgoing_calls_answered": "number",
  "outgoing_calls_unanswered": "number",
  "incoming_calls": "number",
  "incoming_calls_answered": "number",
  "incoming_calls_unanswered": "number",
  "total_calls": "number",
  "unique_leads_engaged": "number"
}
```

#### GET `/api/analytics/seller_call_analytics`
**Description:** Get seller-specific call analytics summary
**Authentication:** JWT required
**Query Parameters:**
- `team_member_ids` (required): Array of team member UUIDs
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `time_frame` (optional, string, **DEPRECATED**) - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:**
```json
{
  "seller_data": [
    {
      "seller_id": "uuid",
      "seller_name": "string", 
      "seller_phone": "string",
      "seller_email": "string",
      "outgoing_calls": "number",
      "outgoing_calls_answered": "number",
      "outgoing_calls_unanswered": "number",
      "incoming_calls": "number",
      "incoming_calls_answered": "number",
      "incoming_calls_unanswered": "number",
      "total_calls": "number",
      "unique_leads_engaged": "number"
    }
  ]
}
```

#### GET `/api/analytics/seller_call_data/<uuid:seller_uuid>`
**Description:** Get comprehensive call data for a specific seller with detailed breakdowns
**Authentication:** JWT required
**Query Parameters:**
- `start_date` (optional, string, format: YYYY-MM-DD) - Start date for filtering
- `end_date` (optional, string, format: YYYY-MM-DD) - End date for filtering  
- `time_frame` (optional, string, **DEPRECATED**) - Values: "today", "yesterday", "this_week", "last_week", "this_month", "last_month"
**Output:**
```json
{
  "seller_id": "uuid",
  "seller_name": "string",
  "seller_phone": "string",
  "sales_data": {
    "hour0": {
      "outgoing_calls": "number",
      "incoming_calls": "number",
      "unique_leads_engaged": "number"
    }
  },
  "total_outgoing_calls": "number",
  "total_incoming_calls": "number",
  "total_unique_leads": "number"
}
```

---

## 11. Performance Analytics

#### POST `/api/performance/call/<meeting_id>/metrics`
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

#### GET `/api/performance/call/<meeting_id>/metrics`
**Description:** Get call performance metrics for a specific meeting
**Authentication:** JWT Required
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
      }
    }
  }
}
```

#### DELETE `/api/performance/call/<meeting_id>/metrics`
**Description:** Delete call performance metrics for a specific meeting (Admin/Manager only)
**Authentication:** JWT Required (Admin/Manager role)
**Output:**
```json
{
  "message": "Call performance metrics deleted successfully"
}
```

#### GET `/api/performance/user/<user_id>/metrics`
**Description:** Get call performance metrics for a user within a date range with daily averages
**Authentication:** JWT Required
**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format (defaults to 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (defaults to today)
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
      "overall_score": 7.5,
      "calls_count": 3
    }
  },
  "period_summary": {
    "total_calls": 15,
    "days_with_data": 8,
    "overall_averages": {
      "intro": 8.1,
      "overall_score": 7.4
    }
  }
}
```

#### GET `/api/performance/user/<uuid:user_id>/calls`
**Description:** Get detailed per-call performance metrics for a specific seller within a date range with pagination support
**Authentication:** JWT required
**Query Parameters:**
- `start_date` (optional): Start date in YYYY-MM-DD format (default: 30 days ago)
- `end_date` (optional): End date in YYYY-MM-DD format (default: today)
- `page` (optional, integer, default: 1) - Page number (1-based)
- `limit` (optional, integer, default: 50, max: 100) - Number of records per page
**Output:**
```json
{
  "message": "User performance calls retrieved successfully",
  "user_info": {
    "user_id": "uuid",
    "name": "string",
    "email": "string"
  },
  "date_range": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD"
  },
  "calls": [
    {
      "meeting_id": "uuid",
      "call_title": "string",
      "buyer_name": "string",
      "buyer_phone": "string",
      "call_start_time": "ISO datetime",
      "duration_minutes": 45.5,
      "detected_products": "array",
      "overall_score": 7.5,
      "analyzed_at": "ISO datetime",
      "metrics": {
        "intro": {
          "score": 8.5,
          "reason": "string"
        }
      },
      "analysis": {
        "product_details_analysis": "object",
        "objection_handling_analysis": "object",
        "overall_performance_summary": "object"
      }
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_count": 500,
    "limit": 50,
    "has_next": true,
    "has_previous": false
  }
}
```

---

## 12. Search & Knowledge Management

#### POST `/api/search/`
**Description:** Semantic search across agency data (meetings, buyers, etc.)
**Authentication:** JWT required
**Input:**
```json
{
  "query": "string",
  "k": 8,
  "types": "array (optional)",
  "seller_id": "uuid (optional)"
}
```
**Output:**
```json
{
  "results": [
    {
      "id": "uuid",
      "content": "string",
      "score": "number",
      "type": "string",
      "metadata": "object"
    }
  ]
}
```

#### POST `/api/search/answer`
**Description:** Get AI-powered answers to questions based on agency data
**Authentication:** JWT required
**Input:**
```json
{
  "query": "string"
}
```
**Output:**
```json
{
  "answer": "string",
  "sources": [
    {
      "id": "uuid",
      "content": "string",
      "type": "string",
      "metadata": "object"
    }
  ]
}
```

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

## Audio Streaming Endpoints

### GET `/api/audio/meetings/<uuid:meeting_id>/audio/stream`
**Description:** Get presigned URL for audio streaming with security and rate limiting
**Authentication:** JWT required
**Query Parameters:**
- `type` (optional): "stream" (default) for inline playback or "download" for file download
**Rate Limit:** 10 requests per minute per user per meeting
**Output:**
```json
{
  "success": true,
  "data": {
    "url": "https://presigned-s3-url...",
    "expires_in": 3600,
    "expires_at": "2024-01-15T15:30:00Z",
    "file_size": 2048576,
    "content_type": "audio/mpeg",
    "last_modified": "2024-01-15T10:30:00Z",
    "meeting_id": "uuid",
    "meeting_title": "Meeting with John Doe",
    "request_type": "stream"
  },
  "rate_limit": {
    "requests_made": 1,
    "requests_remaining": 9,
    "reset_time": "2024-01-15T11:31:00Z"
  }
}
```

### GET `/api/audio/meetings/<uuid:meeting_id>/audio/download`
**Description:** Get presigned URL for audio download (convenience endpoint)
**Authentication:** JWT required
**Rate Limit:** 5 requests per 5 minutes per user per meeting
**Output:** Same as stream endpoint with download-specific headers

### GET `/api/audio/audio/service/status`
**Description:** Get audio streaming service health status
**Authentication:** JWT required
**Output:**
```json
{
  "success": true,
  "data": {
    "service_name": "AudioStreamingService",
    "bucket_name": "chirp-call-recordings",
    "url_expiry_seconds": 3600,
    "aws_region": "ap-south-1",
    "service_status": "active",
    "s3_connectivity": "ok",
    "rate_limiting": "active"
  }
}
```

### GET `/api/audio/audio/user/stats`
**Description:** Get user's audio streaming statistics and rate limit status
**Authentication:** JWT required
**Output:**
```json
{
  "success": true,
  "data": {
    "user_id": "uuid",
    "rate_limiting": "active",
    "active_limits": [
      {
        "meeting_id": "uuid",
        "requests_made": 3,
        "ttl_seconds": 45,
        "reset_time": "2024-01-15T11:31:00Z"
      }
    ],
    "stream_limit": "10 requests per minute per meeting",
    "download_limit": "5 requests per 5 minutes per meeting"
  }
}
```

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
11. Search functionality provides semantic search and AI-powered answers across agency data
12. Date parameters support YYYY-MM-DD format, with time_frame parameters being deprecated in favor of precise date ranges
13. **Pagination Support**: The following endpoints support pagination via `page` and `limit` query parameters:
    - `/api/meetings/call_history` 
    - `/api/buyers/all`
    - `/api/actions/`
    - `/api/performance/user/<uuid>/calls`
    
    **Pagination Parameters:**
    - `page` (optional): Page number, 1-based (default: 1)
    - `limit` (optional): Records per page (default: 50, max: 100)
    
    **Pagination Response Format:**
    ```json
    {
      "pagination": {
        "current_page": 1,
        "total_pages": 10,
        "total_count": 500,
        "limit": 50,
        "has_next": true,
        "has_previous": false
      }
    }
14. Audio streaming uses presigned S3 URLs for secure, direct browser access without server storage. URLs expire after 1 hour and are rate limited to prevent abuse. Managers can access team member meeting audio.
    ```