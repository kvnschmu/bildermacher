import os
import json
import base64
import google.generativeai as genai

# Hilfsfunktion, um den Event Body zuverlässig zu dekodieren
def decode_netlify_body(event):
    body = event['body']
    # Netlify kodiert den Body manchmal Base64, besonders bei komplexen Payloads
    if event.get('isBase64Encoded'):
        # Body wird von base64 dekodiert und in UTF-8 gewandelt
        body = base64.b64decode(body).decode('utf-8')
    return json.loads(body)

def handler(event, context):
    # Nur POST-Anfragen erlauben
    if event['httpMethod'] != 'POST':
        return {'statusCode': 405, 'body': 'Method Not Allowed'}

    try:
        # 1. Daten aus dem Frontend zuverlässig lesen
        body = decode_netlify_body(event)
        image_data = body.get('image')
        mime_type = body.get('mime_type')

        if not image_data:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Kein Bild empfangen'})}

        # 2. API Key aus Umgebungsvariablen holen
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            # DIESER FEHLER TRITT AUF, WENN DIE UMGEBUNGSVARIABLE IM NETLIFY-DASHBOARD FEHLT
            return {'statusCode': 500, 'body': json.dumps({'error': 'API Key fehlt'})}
        
        genai.configure(api_key=api_key)
        # Flash ist schnell und kosteneffizient für Bildanalyse
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # 3. BASE64-DEKODIERUNG EXTREM ROBUST MACHEN
        
        # Leere Zeichen und Zeilenumbrüche entfernen (Wichtig für Netlify/Proxies)
        cleaned_image_data = image_data.strip().replace('\n', '').replace('\r', '')

        # Manuelles Auffüllen des Base64-Strings (Padding-Fix)
        # Base64-Länge muss durch 4 teilbar sein.
        missing_padding = len(cleaned_image_data) % 4
        if missing_padding:
            # Füge die fehlenden '='-Zeichen hinzu
            cleaned_image_data += '=' * (4 - missing_padding)

        # Base64-String in Bytes umwandeln
        try:
            # Versuch 1: Standard Base64 Dekodierung
            image_bytes = base64.b64decode(cleaned_image_data)
        except Exception:
            # Versuch 2: URL-sichere Base64 Dekodierung (falls - und _ anstelle von + und / verwendet werden)
            image_bytes = base64.urlsafe_b64decode(cleaned_image_data)


        # 4. Der SYSTEM-PROMPT
        system_prompt = """
        Du bist ein Experte für KI-Prompts (Midjourney/Stable Diffusion).
        
        DEINE AUFGABE:
        Analysiere das hochgeladene Bild (Stil, Licht, Stimmung, technischer Look).
        Erstelle basierend darauf einen Prompt, der für eine "Image-to-Image" Generierung genutzt wird.
        
        WICHTIGE STRUKTUR DES OUTPUTS (Halte dich exakt daran):
        1. Beginne IMMER mit dem Satzteil: 
           "Ein [Adjektive passend zum Bildstil] Portrait der Person, basierend auf dem hochgeladenen Referenzbild. Detailgetreue Wiedergabe der Gesichtszüge..."
        2. Füge dann die spezifische Analyse des Bildes hinzu:
           - Beschreibe die exakte Beleuchtung (z.B. "sanfte Studiobeleuchtung", "harter Schatten", "Neonlicht").
           - Beschreibe den Hintergrund.
           - Beschreibe die Pose und den Ausdruck.
           - Beschreibe den künstlerischen Stil (z.B. "35mm Analogfilm", "Pixar-Stil", "Ölgemälde", "schwarz-weiß Fotografie").
        3. Ende mit dem Hinweis: 
           "Stil: [Kurze Zusammenfassung des Stils]."

        SPRACHE: Deutsch.
        
        Gib NUR den fertigen Prompt zurück.
        """

        # 5. Generierung
        image_parts = [{"mime_type": mime_type, "data": image_bytes}]
        response = model.generate_content([system_prompt, image_parts[0]])
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'prompt': response.text.strip()})
        }

    except Exception as e:
        # Hier werden alle Fehler abgefangen. Der Wert von 'error' muss im Netlify-Log
        # aufgerufen werden, um die genaue Fehlerursache zu sehen (z.B. 'Incorrect padding').
        return {'statusCode': 500, 'body': json.dumps({'error': str(e), 'debug_message': 'Fehler bei der Funktionsausführung (Prüfe Netlify-Logs)'})}
