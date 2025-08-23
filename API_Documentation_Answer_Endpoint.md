### Universal Search Answer API

This endpoint provides a universal search capability, allowing users to ask natural language questions and receive generated answers. It can handle both knowledge-based questions (retrieving information from call transcripts, summaries, etc.) and analytical questions (calculating metrics and trends).

**Endpoint**

`POST /api/search/answer`

**Authentication**

This endpoint is protected and requires a valid JSON Web Token (JWT) to be included in the `Authorization` header.

*   **Header:** `Authorization: Bearer <JWT_TOKEN>`

**Request Body**

The request body must be a JSON object containing the user's query.

```json
{
  "query": "What were the key objections raised about the new product this month?"
}
```

**Parameters**

| Field   | Type   | Required | Description                                     |
| :------ | :----- | :------- | :---------------------------------------------- |
| `query` | string | Yes      | The natural language question asked by the user. |

**Success Response (200 OK)**

The response is a JSON object containing the generated answer. For knowledge-based questions, it may also include the sources used to formulate the answer.

```json
{
  "answer": "The primary objection was related to the pricing structure, which some customers found confusing compared to competitors.",
  "sources": [
    {
      "id": "uuid-of-semantic-doc-1",
      "type": "meeting.fact",
      "meeting_id": "uuid-of-meeting-1",
      "distance": 0.85
    },
    {
      "id": "uuid-of-semantic-doc-2",
      "type": "meeting.qa",
      "meeting_id": "uuid-of-meeting-2",
      "distance": 0.91
    }
  ]
}
```

**Fields in the `sources` array:**

| Field        | Type   | Description                                                     |
| :----------- | :----- | :-------------------------------------------------------------- |
| `id`         | string | The unique ID of the `semantic_document`.                       |
| `type`       | string | The type of the document (e.g., `meeting.fact`, `meeting.qa`).  |
| `meeting_id` | string | The ID of the meeting the document is associated with.          |
| `distance`   | float  | The semantic similarity score from the vector search (lower is better). |

**Example: cURL Request**

```bash
curl -X POST https://your-api-domain.com/api/search/answer \\
-H "Authorization: Bearer <YOUR_JWT_TOKEN>" \\
-H "Content-Type: application/json" \\
-d '{
      "query": "How many calls did my team make last week?"
    }'
```

**Example: Analytics Response**

For an analytical query, the `sources` array will typically be empty.

```json
{
  "answer": "Your team made a total of 87 calls last week."
}
```
