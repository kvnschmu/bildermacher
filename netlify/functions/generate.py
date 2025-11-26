import os
import json
import base64
import google.generativeai as genai

# Hilfsfunktion, um den Event Body zuverlässig zu dekodieren
def decode_netlify_body(event):
    body = event['body']
    # Netlify kodiert den Body manchmal Base64, besonders bei komplexen Payloads
    if event.get('isBase64Encoded'):
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
            return {'statusCode': 500, 'body': json.dumps({'error': 'API Key fehlt'})}
        
        genai.configure(api_key=api_key)
        # Flash ist schnell und kosteneffizient für Bildanalyse
        model = genai.GenerativeModel('gemini-2.5-flash-lite')

        # 3. Der SYSTEM-PROMPT (Das Herzstück)
        # Hier definieren wir exakt, dass der Output für Referenz-Bild-Generierung sein muss.
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
        
        Beispiel für den gewünschten Output-Tonfall (aber angepasst an das analysierte Bild):
        "Ein hyperrealistisches, hochauflösendes Portrait der Person, basierend auf dem hochgeladenen Referenzbild. Detailgetreue Wiedergabe der Gesichtszüge. Das Bild zeigt eine dramatische Beleuchtung von der Seite, starke Kontraste. Der Ausdruck ist ernst. Stil: Film Noir Ästhetik."
        
        Gib NUR den fertigen Prompt zurück.
        """

        # 4. Bild vorbereiten (mit robusterer Base64-Dekodierung)
        # Wir müssen sicherstellen, dass wir gültiges Base64 an b64decode übergeben,
        # besonders wichtig ist es, Leerzeichen zu entfernen, die manchmal eingefügt werden.
        cleaned_image_data = image_data.strip().replace('\n', '').replace('\r', '')

        # Hier verwenden wir die Standard-Base64-Dekodierung
        image_bytes = base64.b64decode(cleaned_image_data)
        
        image_parts = [{"mime_type": mime_type, "data": image_bytes}]

        # 5. Generierung
        response = model.generate_content([system_prompt, image_parts[0]])
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'prompt': response.text.strip()})
        }

    except Exception as e:
        # Hier werden alle Fehler (inkl. Base64-Dekodierfehlern) abgefangen.
        # Im Netlify Function Log sehen Sie nun den genauen Fehler, falls es nicht
        # an der Body-Dekodierung liegt.
        return {'statusCode': 500, 'body': json.dumps({'error': str(e), 'debug_message': 'Fehler bei der Funktionsausführung'})}
