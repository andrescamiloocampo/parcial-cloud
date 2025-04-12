from flask import Flask, request, jsonify, render_template_string
import boto3
import uuid
import pytesseract
from PIL import Image
import io
import json
import re

app = Flask(__name__)

s3 = boto3.client('s3',
    region_name='us-east-1'
)

BUCKET_ENTRADA = 'andres-images-ocr'
BUCKET_SALIDA = 'andres-json-ocr'

UPLOAD_FORM = """
<!doctype html>
<title>Subir Recibo</title>
<h1>Subir imagen de recibo</h1>
<form method=post enctype=multipart/form-data action="/upload">
  <input type=file name=file>
  <input type=submit value=Subir>
</form>
"""

@app.route('/')
def index():
    return render_template_string(UPLOAD_FORM)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    filename = f"{uuid.uuid4()}.png"

    s3.upload_fileobj(file, BUCKET_ENTRADA, filename)

    return jsonify({'mensaje': 'Imagen subida correctamente', 'archivo': filename})

@app.route('/procesar', methods=['GET'])
def procesar():
    bucket = BUCKET_ENTRADA
    nombre_archivo = request.args.get('file')

    if not bucket or not nombre_archivo:
        return jsonify({'error': 'Faltan parametros: bucket y nombre_archivo'}), 400

    try:
        response = s3.get_object(Bucket=bucket, Key=nombre_archivo)
        imagen = Image.open(io.BytesIO(response['Body'].read()))

        texto = pytesseract.image_to_string(imagen, lang='spa')
        datos = extraer_datos(texto)

        salida_key = nombre_archivo.replace('.png', '.json')
        json_bytes = io.BytesIO(json.dumps(datos, indent=2).encode('utf-8'))
        s3.upload_fileobj(json_bytes, BUCKET_SALIDA, salida_key)

        return jsonify({'mensaje': 'Datos procesados y subidos', 'datos': datos})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def extraer_datos(texto):
    datos = {}

    num_match = re.search(r'(N[úu]mero|N\u00ba|#)\s*[:\-]?\s*(\d+)', texto, re.IGNORECASE)
    fecha_match = re.search(r'(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})', texto)
    total_match = re.search(r'(Total|TOTAL)\s*[:\-]?\s*\$?\s*([\d,.]+)', texto)
    restaurante_match = re.search(r'Restaurante\s*[:\-]?\s*(.+)', texto, re.IGNORECASE)

    if num_match:
        datos['numero_recibo'] = num_match.group(2)
    if fecha_match:
        datos['fecha'] = fecha_match.group(1)
    if total_match:
        datos['total'] = total_match.group(2)
    if restaurante_match:
        datos['restaurante'] = restaurante_match.group(1).strip()

    return datos

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)