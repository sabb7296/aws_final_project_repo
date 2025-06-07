import boto3
import mysql.connector
from flask import Flask, request, render_template
from werkzeug.utils import secure_filename
import base64
from io import BytesIO

# Gemini API removed from app.py — handled via Lambda

# Flask app setup
app = Flask(__name__)

# AWS S3 Configuration
S3_BUCKET = "image-caption-app-bucket27"
S3_REGION = "us-east-1"
UPLOADS_PREFIX = "uploads/"
THUMBNAILS_PREFIX = "thumbnails/"

def get_s3_client():
    return boto3.client("s3", region_name=S3_REGION)

# RDS Configuration
DB_HOST = "image-caption-db.cj49celnu5hq.us-east-1.rds.amazonaws.com"
DB_NAME = "image_caption_db"
DB_USER = "admin"
DB_PASSWORD = "Imagec4p12345!"

def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        return connection
    except mysql.connector.Error as err:
        print("Error connecting to database:", err)
        return None

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def upload_form():
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload_image():
    if request.method == "POST":
        if "file" not in request.files:
            return render_template("upload.html", error="No file selected")

        file = request.files["file"]
        if file.filename == "":
            return render_template("upload.html", error="No file selected")
        if not allowed_file(file.filename):
            return render_template("upload.html", error="Invalid file type")

        filename = secure_filename(file.filename)
        file_data = file.read()
        uploads_key = f"{UPLOADS_PREFIX}{filename}"

        try:
            s3 = get_s3_client()
            s3.upload_fileobj(BytesIO(file_data), S3_BUCKET, uploads_key)
        except Exception as e:
            return render_template("upload.html", error=f"S3 Upload Error: {str(e)}")

        encoded_image = base64.b64encode(file_data).decode("utf-8")
        file_url = f"https://{S3_BUCKET}.s3.{S3_REGION}.amazonaws.com/{uploads_key}"

        caption = "Caption will be generated shortly by Lambda."

        return render_template("upload.html", image_data=encoded_image, file_url=file_url, caption=caption)

    return render_template("upload.html")

@app.route("/gallery")
def gallery():
    try:
        connection = get_db_connection()
        if connection is None:
            return render_template("gallery.html", error="Database Error: Unable to connect to the database.")
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT image_key, caption FROM captions ORDER BY uploaded_at DESC")
        results = cursor.fetchall()
        connection.close()

        images_with_captions = []
        for row in results:
            image_key = f"{UPLOADS_PREFIX}{row['image_key']}"
            thumbnail_key = f"{THUMBNAILS_PREFIX}{row['image_key']}"

            s3 = get_s3_client()
            image_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": image_key},
                ExpiresIn=3600
            )
            thumbnail_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": S3_BUCKET, "Key": thumbnail_key},
                ExpiresIn=3600
            )

            images_with_captions.append({
                "image_url": image_url,
                "thumbnail_url": thumbnail_url,
                "caption": row["caption"]
            })

        return render_template("gallery.html", images=images_with_captions)

    except Exception as e:
        return render_template("gallery.html", error=f"Database Error: {str(e)}")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
