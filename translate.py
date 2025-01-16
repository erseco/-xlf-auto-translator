import argparse
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pydub import AudioSegment
import replicate
import requests
import base64
import boto3
from botocore.exceptions import ClientError
import uuid

# Cargar variables de entorno desde el archivo .env
load_dotenv()

# Configurar S3
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    region_name=os.getenv('AWS_REGION', 'eu-west-1')
)

# Configurar la API de Replicate
api_token = os.getenv("REPLICATE_API_TOKEN")
hedgedoc_base_url = os.getenv("HEDGEDOCS_URL")
fileio_token = os.getenv("FILEIO_API_TOKEN")
pixeldrain_token = os.getenv("PIXELDRAIN_API_TOKEN")

def upload_to_s3(file_path):
    """
    Sube un archivo a S3 y devuelve una tupla con la URL pública temporal y la información para eliminar el archivo
    """
    try:
        bucket_name = os.getenv('AWS_BUCKET_NAME')
        # Generar un nombre único para el archivo
        file_name = f"audio_temp/{str(uuid.uuid4())}{os.path.splitext(file_path)[1]}"
        
        # Subir el archivo a S3
        s3_client.upload_file(file_path, bucket_name, file_name)
        
        # Generar URL temporal (1 hora)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_name
            },
            ExpiresIn=3600  # 1 hora
        )
        
        return url, {'bucket': bucket_name, 'key': file_name}
        
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise

def delete_from_s3(bucket_name, key):
    """
    Elimina un archivo de S3
    """
    try:
        s3_client.delete_object(Bucket=bucket_name, Key=key)
    except Exception as e:
        print(f"Error deleting from S3: {e}")


def convert_to_mp3(file_path, replace=False):
    mp3_path = os.path.splitext(file_path)[0] + ".mp3"
    if os.path.exists(mp3_path) and not replace:
        print(f"Error: The MP3 file {mp3_path} already exists. Use --replace to overwrite it.")
        return None
    try:
        audio = AudioSegment.from_file(file_path)
        # Usamos 128k para voz hablada, mono channel para reducir tamaño
        audio = audio.set_channels(1)
        audio.export(mp3_path, format="mp3", parameters=["-q:a", "0", "-b:a", "128k"])
        return mp3_path
    except Exception as e:
        print("Error converting audio to MP3:", e)
        raise

def transcribe_audio(wav_url, language, model):
    try:
        output = replicate.run(

            # "vaibhavs10/incredibly-fast-whisper:3ab86df6c8f54c11309d4d1f930ac292bad43ace52d10c80d87eb258b3c9f79c",
            "turian/insanely-fast-whisper-with-video:4f41e90243af171da918f04da3e526b2c247065583ea9b757f2071f573965408",


            # "openai/whisper:be69de6b9dc57b3361dff4122ef4d6876ad4234bf5c879287b48d35c20ce3e83",
            input={
                "task": "transcribe",
                "audio": wav_url,
                "language": "spanish"
            }
        )
        return output["text"]
        # return output["transcription"]

    except Exception as e:
        print("Error transcribing audio:", e)
        raise

def save_transcription(text, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

# Función para obtener el nombre del mes en español
def get_month_name(month):
    months = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"
    ]
    return months[month - 1]

def generate_minutes_template(transcription):

    # Obtener la fecha actual
    current_date = datetime.now()
    day = current_date.day
    month = get_month_name(current_date.month)
    year = current_date.year

    # Formatear la fecha en español
    formatted_date = f"{day} de {month} de {year}"

    prompt = f"""
    Rellena un acta de reunión basada en elresumen de la siguiente transcripción:

    ---
    Transcripción completa:
    {transcription}
    ---

    El acta debe cumplir el siguiente formato:
    ---
    # Acta de la Reunión ({formatted_date})

    **Fecha:** {formatted_date}

    **Asistentes:**

    - **ATE:** Ernesto

    ## Resumen de la Reunión

    ### Puntos Más Importantes:

    ## Acuerdos

    ## Pasos Futuros

    ## Transcripción Completa
    ```
    (pegar transcripción manualmente)
    ```

    El acta debe ser en español, y no quiero que incluyas ni un texto introductorio ni nada adicional, limítate a rellenar el acta.
    """


    return prompt


def save_minutes(minutes, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(minutes)

def upload_to_hedgedoc(content):
    hedgedoc_url = hedgedoc_base_url + "/new"  # URL de tu instancia de HedgeDoc
    headers = {
        "Content-Type": "text/markdown",
    }

    try:
        response = requests.post(hedgedoc_url, data=content, headers=headers)
        response.raise_for_status()

        document_url = response.url
        return document_url

    except requests.RequestException as e:
        print("Error uploading to HedgeDoc:", e)
        raise

def process_file(audio_path, language, model, replace):
    if not os.path.exists(audio_path):
        raise ValueError(f"The input file {audio_path} does not exist.")

    # Define the output path
    output_base_path = os.path.splitext(audio_path)[0]
    output_transcription_path = output_base_path + '-' + model + '.txt'
    output_minutes_path = output_base_path + '-' + model + '-acta.md'

    # Check if the output file already exists
    if os.path.exists(output_transcription_path) and not replace:
        print(f"Error: The output file {output_transcription_path} already exists. Use --replace to overwrite it.")
        return

    # Convert the audio to MP3 format if it's not already in MP3 format
    if not audio_path.lower().endswith('.mp3'):
        try:
            print(f"Converting {audio_path} to MP3 format...")
            mp3_path = convert_to_mp3(audio_path, replace)
            if mp3_path is None:
                return  # Stop if the MP3 file already exists and --replace is not specified
        except Exception as e:
            print(f"Error converting {audio_path} to MP3: {e}")
            return
    else:
        mp3_path = audio_path

    try:

        print(f"Uploading {mp3_path} to S3...")
        audio_url, s3_info = upload_to_s3(mp3_path)

        print(f"MP3 file uploaded to: {audio_url}")

        try:
            print(f"Starting transcription for {mp3_path}...")
            transcription = transcribe_audio(audio_url, language, model)
        finally:
            # Eliminar el archivo de S3 después de la transcripción
            delete_from_s3(s3_info['bucket'], s3_info['key'])
        save_transcription(transcription, output_transcription_path)

        print(f"Generating minutes for {mp3_path}...")
        minutes = generate_minutes_template(transcription)
        save_minutes(minutes, output_minutes_path)

        # print(f"Uploading minutes to HedgeDoc...")
        # document_url = upload_to_hedgedoc(minutes)
        # print(f"Document URL: {document_url}")

        print(f"Transcription saved to {output_transcription_path}")
        # print(f"Minutes saved to {output_minutes_path}")

    except KeyboardInterrupt:
        print("\nTranscription interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Failed to transcribe audio {audio_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Transcribe MP3, WAV, WEBM, or MP4 audio files to text using Replicate API.")
    parser.add_argument("input_path", help="Path to the audio file or directory containing audio files to transcribe")
    parser.add_argument("--language", default="es", help="Language of the audio for transcription (default=es)")
    parser.add_argument("--model", default="whisper-1", help="Whisper model to use for transcription (default=whisper-1)")
    parser.add_argument("--output_format", default="txt", choices=['txt'], help="Output format for the transcription (default=txt)")
    parser.add_argument("--replace", action='store_true', help="Replace the output file if it already exists")
    args = parser.parse_args()

    input_path = args.input_path

    if os.path.isdir(input_path):
        for root, _, files in os.walk(input_path):
            for file in files:
                if file.lower().endswith(('.mp3', '.wav', '.webm', '.mp4', '.mpga', '.mpeg', '.m4a', '.weba')):
                    audio_path = os.path.join(root, file)
                    process_file(audio_path, args.language, args.model, args.replace)
    else:
        process_file(input_path, args.language, args.model, args.replace)

if __name__ == "__main__":
    main()
