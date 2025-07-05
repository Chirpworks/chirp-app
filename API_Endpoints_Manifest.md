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

#### GET `/user/get_team`
**Description:** Get team members and their call statistics
**Authentication:** JWT required
**Input:** None
**Output:**
```json
{
  "team_members": [
    {
      "name": "string",
      "email": "string",
      "id": "uuid",
      "phone": "string",
      "total_outgoing_calls": "integer",
      "total_incoming_calls": "integer", 
      "unanswered_outgoing_calls": "integer",
      "unique_leads_engaged": "integer",
      "unique_leads_called": "integer"
    }
  ],
  "total_outgoing_calls": "integer",
  "total_incoming_calls": "integer",
  "total_unanswered_outgoing_calls": "integer", 
  "total_unique_leads_engaged": "integer",
  "total_unique_leads_called": "integer"
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
- Query: `team_member_id` (optional, array of UUIDs)
**Output:** Call history data

#### GET `/meetings/call_data/<meeting_id>`
**Description:** Get detailed meeting data by ID
**Authentication:** JWT required
**Input:**
- Path: `meeting_id` (UUID)
- Query: `team_member_id` (optional, UUID)
**Output:** Meeting data with job details

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

---

## 5. Buyer Management

### 5.1 Buyer Profile Operations

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
  "products_discussed": "string"
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
  "products_discussed": "string"
}
```
**Output:** Updated buyer profile

#### GET `/buyers/call_history/<buyer_id>`
**Description:** Get call history for a buyer
**Authentication:** JWT required
**Input:**
- Path: `buyer_id` (UUID)
**Output:** Call history data

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
**Description:** Get actions for user or team members
**Authentication:** JWT required
**Input:**
- Query: `team_member_id` (optional, array of UUIDs)
**Output:** Actions data

#### GET `/actions/<action_id>`
**Description:** Get specific action by ID
**Authentication:** JWT required
**Input:**
- Path: `action_id` (UUID)
**Output:** Action data

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