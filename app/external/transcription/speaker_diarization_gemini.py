import json
import subprocess
import tempfile
from urllib.parse import urlparse

import logging
import os
from google import genai
import boto3
import requests

from app import Job
from app import Meeting
from app.models.job import JobStatus

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variable for JOB_ID (provided by ECS via container overrides)
JOB_ID = os.environ.get("JOB_ID")
DATABASE_URL = os.environ.get("STAGING_DATABASE_URL")  # kept for backward compatibility
FLASK_API_URL = os.getenv("FLASK_API_URL")

# Initialize AWS S3 client
s3_client = boto3.client("s3")

# Note: Database connection removed - now using API calls for context retrieval
if DATABASE_URL:
    logger.info("DATABASE_URL provided but using API-based context retrieval instead")
if not FLASK_API_URL:
    logger.warning("FLASK_API_URL not provided - enhanced transcription context will not be available")


def get_context_for_transcription(job_id):
    """Retrieve agency, buyer, seller, and product info for enhanced transcription via API calls"""
    if not FLASK_API_URL:
        logger.warning("FLASK_API_URL not provided - cannot fetch context via API")
        return None, None, None, None
        
    try:
        # Get full context via the new context endpoint
        logger.info(f"Fetching context for job_id: {job_id} via API")
        context_response = requests.get(f"{FLASK_API_URL}/api/jobs/{job_id}/context", timeout=15)
        
        if context_response.status_code != 200:
            logger.error(f"Failed to fetch job context: {context_response.status_code} - {context_response.text}")
            return None, None, None, None
            
        context_data = context_response.json()
        
        # Extract the context components
        agency_info = context_data.get('agency_info')
        buyer_info = context_data.get('buyer_info') 
        seller_info = context_data.get('seller_info')
        product_catalogue = context_data.get('product_catalogue', [])
        
        logger.info(f"Retrieved context via API for job {job_id}: Agency={agency_info.get('name') if agency_info else 'None'}, Buyer={buyer_info.get('name') if buyer_info else 'None'}, Seller={seller_info.get('name') if seller_info else 'None'}, Products={len(product_catalogue)}")
        
        return agency_info, buyer_info, seller_info, product_catalogue
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed while fetching context for job {job_id}: {e}")
        return None, None, None, None
    except Exception as e:
        logger.error(f"Error retrieving context via API for job {job_id}: {e}")
        return None, None, None, None


def create_enhanced_prompt(agency_info, buyer_info, seller_info, product_catalogue):
    """Create an enhanced transcription prompt with agency-specific context"""
    
    # Extract context information with defaults
    agency_name = agency_info.get('name', 'the company') if agency_info else 'the company'
    agency_description = agency_info.get('description', '') if agency_info else ''
    
    buyer_name = buyer_info.get('name', 'buyer') if buyer_info and buyer_info.get('name') else 'buyer'
    seller_name = seller_info.get('name', 'seller') if seller_info and seller_info.get('name') else 'seller'
    
    # Extract product names (limit to prevent prompt bloat)
    product_names = []
    if product_catalogue:
        product_names = [p.get('name', '') for p in product_catalogue if p.get('name')]
    
    product_list = ', '.join(product_names) if product_names else 'various products and services'
    
    # Generate industry context based on agency description and products
    industry_terms = []
    if agency_description:
        if any(term in agency_description.lower() for term in ['education', 'school', 'student']):
            industry_terms.extend(['curriculum', 'principal', 'school board', 'academic year', 'enrollment', 'classroom'])
        if any(term in agency_description.lower() for term in ['technology', 'technical', 'digital']):
            industry_terms.extend(['installation', 'technical support', 'warranty', 'maintenance', 'specifications'])
        if any(term in agency_description.lower() for term in ['cultural', 'art', 'music', 'dance']):
            industry_terms.extend(['workshops', 'competitions', 'performances', 'traditional arts', 'heritage'])
    
    industry_context = ', '.join(industry_terms) if industry_terms else 'business terminology'
    
    prompt = f"""You are a professional call transcription expert specializing in {agency_name} business calls.

CALL CONTEXT:
- Agency: {agency_name} - {agency_description}
- Seller: {seller_name} (sales representative from {agency_name})
- Buyer: {buyer_name} (potential customer/client)
- Products discussed may include: {product_list}
- Industry terminology: {industry_context}

TRANSCRIPTION REQUIREMENTS:
1. ACCURACY: Transcribe with high precision, handling multiple languages
2. SPEAKER IDENTIFICATION: Clearly identify {seller_name} vs {buyer_name}
3. ROLE CLASSIFICATION: Classify speakers as "seller" or "buyer" based on context
4. LANGUAGE SUPPORT: English, Hindi, Punjabi, Tamil, Telugu, Malayalam with regional variations
5. TRANSLATION: Provide English translation for non-English segments

ENHANCED LANGUAGE HANDLING:
- Hindi Business Terms: Recognize व्यापार (vyapar), कारोबार (karobar), धंधा (dhanda), बिजनेस (business), सौदा (sauda), दाम (daam), कीमत (keemat)
- Punjabi Sales Context: ਵਪਾਰ (vapar), ਕੰਮ (kamm), ਕਾਰੋਬਾਰ (karobar), ਧੰਦਾ (dhanda), ਪੈਸਾ (paisa)
- PRESERVE English Technical Terms: Keep exact spelling for product names, technical specifications, model numbers
- Currency Format: Always use ₹X,XXX format, X% for percentages, X lakh/crore for large numbers
- Mixed Language Fluency: Handle seamless English-Hindi switching common in business calls
- Regional Variations: Account for different Hindi/Punjabi accents and colloquialisms

AUDIO QUALITY & SYSTEM MESSAGE HANDLING:
- Unclear Speech: Mark [UNCLEAR] with confidence: "low", provide best guess in brackets
- Background Noise: Focus on primary conversation, ignore environmental sounds, phone static
- Overlapping Speech: Create separate entries for simultaneous speakers with [OVERLAPPING] notation
- Phone Artifacts: Ignore connection sounds, beeps, dial tones, call waiting sounds

CRITICAL - SYSTEM MESSAGE EXCLUSION (DO NOT INCLUDE IN TRANSCRIPT):
- "The person you are speaking with has put your call on hold. Please stay on the line."
- "आपको जिस व्यक्ति से बात कर रहे हैं, उसने आपकी कॉल को होल्ड पर रखा है। कृपया लाइन पर बने रहें।"
- Hold music descriptions, elevator music, background music
- "Call recording started", "Call recording stopped"
- "Press 1 for...", "Dial 0 for operator" - any IVR messages
- Connection establishment sounds, call termination beeps
- "Please hold while we connect you", "Connecting your call"
- Mark these as speaker_role: "system" and EXCLUDE from final JSON output

ENHANCED SPEAKER CLASSIFICATION:
- SELLER ({seller_name}): Product presentations, pricing discussions, benefit explanations, objection handling, follow-up scheduling, technical demonstrations, installation details
- BUYER ({buyer_name}): Requirements expression, budget inquiries, decision timeline, approval process discussions, stakeholder consultations, technical questions
- Context Clues for Classification:
  * Seller: Uses product terminology, discusses pricing, handles objections, proposes solutions
  * Buyer: Asks questions, expresses concerns, mentions budget/approval, discusses requirements

PRODUCT-SPECIFIC RECOGNITION:
- Preserve exact product names: {product_list}
- Technical specifications: sizes, models, features, pricing
- Installation and support terms specific to {agency_name}

OUTPUT FORMAT - Return ONLY valid JSON array:
[
  {{
    "speaker": "speaker_1|speaker_2",
    "role": "seller|buyer", 
    "text": "Exact transliteration with preserved technical terms",
    "translation": "English translation if non-English original, null if already English",
    "confidence": "high|medium|low"
  }}
]

CRITICAL VALIDATION REQUIREMENTS:
- Ensure {seller_name} is consistently identified as "seller" role
- Ensure {buyer_name} is consistently identified as "buyer" role  
- Preserve all product names exactly as listed: {product_list}
- Maintain strict chronological order of conversation
- Return ONLY valid JSON format with no markdown formatting or additional text
- Exclude all system messages and automated voice prompts
- Handle currency amounts with proper ₹ formatting
- Mark unclear audio segments appropriately with low confidence"""

    return prompt


def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = ['ffmpeg', '-y', '-i', mp3_path, '-ar', '16000', '-ac', '1', wav_path]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return wav_path


def notify_flask_server(job_id):
    url = f"{FLASK_API_URL}/api/analysis/trigger_analysis"
    requests.post(url, json={"job_id": job_id})


def update_job_status(job_id, status):
    """
    Updates the job status via API endpoint.
    """
    try:
        # Use API endpoint to update job status
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/update_status"
        
        payload = {
            "job_id": job_id,
            "status": status.value
        }
        
        response = requests.post(endpoint, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Updated job {job_id} with status {status.value} via API")
        else:
            logger.error(f"Failed to update job {job_id} status via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database update if API fails
            logger.info(f"Falling back to direct database update for job {job_id}")
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job:
                job.status = status
                # session.commit() # session is removed
                logger.info(f"Updated job {job_id} with status {status.value} via database fallback")
            else:
                logger.error(f"Job {job_id} not found in database fallback")
                
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database update if API request fails
        logger.info(f"Falling back to direct database update for job {job_id}")
        try:
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job:
                job.status = status
                # session.commit() # session is removed
                logger.info(f"Updated job {job_id} with status {status.value} via database fallback")
            else:
                logger.error(f"Job {job_id} not found in database fallback")
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            raise db_ex
    except Exception as ex:
        logger.exception(f"Error updating job status for job {job_id}: {ex}")
        raise ex


def get_audio_url(job_id):
    """
    Gets the S3 URL for the audio file for the given job_id via API endpoint.
    """
    try:
        # Use API endpoint to get audio URL
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/{job_id}/audio_url"
        
        response = requests.get(endpoint, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Retrieved audio URL for job {job_id} via API")
            return data['s3_audio_url']
        else:
            logger.error(f"Failed to get audio URL for job {job_id} via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database query if API fails
            logger.info(f"Falling back to direct database query for job {job_id}")
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job and job.s3_audio_url:
                logger.info(f"Retrieved audio URL for job {job_id} via database fallback")
                return job.s3_audio_url
            else:
                raise ValueError(f"No audio URL found for job_id {job_id}")


    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database query if API request fails
        logger.info(f"Falling back to direct database query for job {job_id}")
        try:
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job and job.s3_audio_url:
                logger.info(f"Retrieved audio URL for job {job_id} via database fallback")
                return job.s3_audio_url
            else:
                raise ValueError(f"No audio URL found for job_id {job_id}")
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            raise db_ex
    except Exception as ex:
        logger.exception(f"Error getting audio URL for job {job_id}: {ex}")
        raise ex


def parse_s3_url(s3_url):
    """
    Parses an S3 URL in the form s3://bucket/key and returns (bucket, key).
    """
    try:
        parsed = urlparse(s3_url)
        if parsed.scheme != "s3":
            raise ValueError("Invalid S3 URL")
        bucket = parsed.netloc
        key = parsed.path.lstrip('/')
        return bucket, key
    except Exception as e:
        logger.error(f"Error parsing S3 url: {s3_url}")
        raise e


def process_audio(job_id, bucket, key):
    """
    Downloads the audio file from S3 using the URL retrieved from the database,
    processes it using WhisperX for diarization, and updates the corresponding
    meeting record with the transcript.
    """
    try:
        update_job_status(job_id, JobStatus.IN_PROGRESS)

        logger.info(f"Fetching audio file from S3: bucket={bucket}, key={key}")

        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            local_audio_path = tmp_file.name

        logger.info(f"Downloading audio file from S3: bucket={bucket}, key={key}")
        mp3_path = local_audio_path.replace('.wav', '.mp3')
        s3_client.download_file(bucket, key, mp3_path)
        local_audio_path = convert_mp3_to_wav(mp3_path)
        logger.info(f"Audio file downloaded to {local_audio_path}")

        transcription, diarization = transcribe_and_diarize(local_audio_path, job_id)
        logger.info(f"Transcription completed with {len(diarization)} segments for job {job_id}")
    except Exception as e:
        logger.error(f"Error while transcribing audio file for job_id: {job_id}. Error: {e}")
        raise e

    # Update the meetings table with the transcript and timestamp
    try:
        # Use API endpoint to update meeting transcription
        api_url = FLASK_API_URL
        endpoint = f"{api_url}/api/jobs/{job_id}/meeting/transcription"
        
        payload = {
            "transcription": json.dumps(diarization)
        }
        
        response = requests.put(endpoint, json=payload, timeout=30)
        
        if response.status_code == 200:
            logger.info(f"Updated meeting transcription for job {job_id} via API")
            logger.info(f"Transcription completed for job {job_id}. Ready for analysis.")
        else:
            logger.error(f"Failed to update meeting transcription for job {job_id} via API. Status: {response.status_code}, Response: {response.text}")
            # Fallback to direct database update if API fails
            logger.info(f"Falling back to direct database update for job {job_id}")
            meeting = None
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job:
                meeting = None # session.query(Meeting).filter_by(id=job.meeting_id).first() # session is removed
            if meeting:
                meeting.transcription = json.dumps(diarization)
                # session.commit() # session is removed
                logger.info(f"Updated meeting {meeting.id} with transcript via database fallback.")
                logger.info(f"Transcription completed for job {job_id}. Ready for analysis.")
            else:
                logger.error(f"Meeting not found for job {job_id}.")
                update_job_status(job_id, JobStatus.FAILURE)

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed for job {job_id}: {e}")
        # Fallback to direct database update if API request fails
        logger.info(f"Falling back to direct database update for job {job_id}")
        try:
            meeting = None
            job = None # session.query(Job).filter_by(id=job_id).first() # session is removed
            if job:
                meeting = None # session.query(Meeting).filter_by(id=job.meeting_id).first() # session is removed
            if meeting:
                meeting.transcription = json.dumps(diarization)
                # session.commit() # session is removed
                logger.info(f"Updated meeting {meeting.id} with transcript via database fallback.")
                logger.info(f"Transcription completed for job {job_id}. Ready for analysis.")
            else:
                logger.error(f"Meeting not found for job {job_id}.")
                update_job_status(job_id, JobStatus.FAILURE)
        except Exception as db_ex:
            logger.exception(f"Database fallback also failed for job {job_id}: {db_ex}")
            update_job_status(job_id, JobStatus.FAILURE)
            raise db_ex
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        raise


def transcribe_and_diarize(audio_file_path, job_id=None):
    """Enhanced transcription with agency-specific context"""
    API_KEY = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=API_KEY)

    audio_file = client.files.upload(file=audio_file_path)

    # Get context information for enhanced transcription
    agency_info, buyer_info, seller_info, product_catalogue = get_context_for_transcription(job_id)
    
    # Create enhanced prompt with context
    if agency_info or buyer_info or seller_info or product_catalogue:
        prompt = create_enhanced_prompt(agency_info, buyer_info, seller_info, product_catalogue)
        logger.info(f"Using enhanced prompt with agency context: {agency_info.get('name') if agency_info else 'Unknown'}")
    else:
        # Fallback to original prompt if context retrieval fails
        prompt = """You are a professional call transcription and analysis expert. Please transcribe and analyze this business call recording.

CONTEXT: This is a business call between a seller (sales representative) and a buyer (potential customer). The call may contain sales discussions, product presentations, negotiations, or customer service interactions.

TASK: Please provide a detailed transcription with speaker diarization and classification.

REQUIREMENTS:
1. Transcribe the audio accurately, handling multiple languages (English, Hindi, Punjabi, Tamil, Telugu, Malayalam)
2. Provide English transliteration for all non-English speech
3. Identify and separate speakers clearly
4. Classify each speaker as either "buyer" or "seller" based on context clues
5. Provide English translation for non-English segments
6. Maintain chronological order of speech

OUTPUT FORMAT: Return ONLY a valid JSON array with this exact structure:
[
  {
    "speaker_id": "speaker_1",
    "speaker_role": "buyer|seller",
    "text": "English transliteration of what was said",
    "translation": "English translation if original was not in English",
    "timestamp_start": "approximate_start_time",
    "timestamp_end": "approximate_end_time",
    "confidence": "high|medium|low"
  }
]

CLASSIFICATION GUIDELINES:
- SELLER: Person presenting products/services, asking qualifying questions, discussing pricing, following up on leads
- BUYER: Person asking about products/services, expressing needs/concerns, negotiating terms, making purchasing decisions

IMPORTANT: 
- Return ONLY the JSON array, no additional text or markdown formatting
- Ensure JSON is properly formatted and valid
- If uncertain about speaker role, use context clues from the conversation
- Handle overlapping speech by creating separate entries
- Mark unclear speech with low confidence"""
        logger.info("Using fallback prompt due to context retrieval failure")

    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20", 
        contents=[prompt, audio_file]
    )

    # Improved JSON parsing with enhanced validation
    response_text = response.text
    if response_text is None:
        raise ValueError("Empty response from Gemini API")
    response_text = response_text.strip()
    logger.info(f"Raw Gemini response length: {len(response_text)} characters")
    
    # Remove any markdown formatting if present
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0]
    elif "```" in response_text:
        response_text = response_text.split("```")[1]
    
    response_text = response_text.strip()
    logger.info(f"Cleaned response text length: {len(response_text)} characters")
    
    try:
        parsed_response = json.loads(response_text)
        
        # Validate and process the response with enhanced filtering
        transcription = ''
        diarization = []
        
        for segment in parsed_response:
            # Skip system messages and automated voices
            speaker_role = segment.get('speaker_role', segment.get('role', 'unknown'))
            if speaker_role == 'system':
                logger.info("Skipping system message segment")
                continue
                
            # Build full transcription
            segment_text = segment.get('text', '')
            if segment_text and not any(phrase in segment_text.lower() for phrase in [
                'call on hold', 'stay on the line', 'होल्ड पर रखा है', 'लाइन पर बने रहें'
            ]):
                transcription += segment_text + ' '
            
            # Validate and clean segment
            clean_segment = {
                'speaker': segment.get('speaker_id', segment.get('speaker', 'unknown')),
                'role': speaker_role,
                'text': segment_text,
                'translation': segment.get('translation', ''),
                'confidence': segment.get('confidence', 'medium')
            }
            
            # Only add non-system segments
            if speaker_role in ['seller', 'buyer'] and segment_text:
                diarization.append(clean_segment)
        
        logger.info(f"Successfully processed {len(diarization)} segments (system messages filtered)")
        return transcription.strip(), diarization
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Raw response: {response_text}")
        raise ValueError(f"Invalid JSON response from Gemini: {e}")


def run_diarization(job_id):
    if not job_id:
        logger.error("Missing required environment variable JOB_ID. Exiting.")
        exit(1)

    try:
        logger.info(f"Fetching audio URL for job {job_id}")
        s3_url = get_audio_url(job_id)
        logger.info(f"Retrieved audio URL: {s3_url}")
    except Exception as e:
        logger.exception(f"Error retrieving audio URL for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)
    try:
        logger.info(f"Parsing s3_audio_url: {s3_url}")
        bucket, key = parse_s3_url(s3_url)
    except Exception as e:
        logger.exception(f"Error in parsing S3 audio URL: {s3_url} for job {job_id}: {e}")
        update_job_status(job_id, JobStatus.FAILURE)
        exit(1)

    try:
        logger.info(f"Processing job {job_id} for audio file {s3_url}")
        process_audio(job_id, bucket, key)
    except Exception as e:
        logger.error(f"Error in processing diarization for job {job_id}.")
        update_job_status(job_id, JobStatus.FAILURE)

    try:
        notify_flask_server(job_id)
        logger.info(f"Sent a message to the flask server to start analysis for job_id: {job_id}")
    except Exception as e:
        logger.exception(f"Failed to notify flask server to start analysis for job_ID: {job_id}")


if __name__ == "__main__":
    run_diarization(JOB_ID)
