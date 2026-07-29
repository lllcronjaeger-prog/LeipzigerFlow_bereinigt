LeipzigerFlow S1.3 PR-008 – Ollama Local First
===============================================

Änderungen
----------
- Ollama ist der Standardanbieter für neue Installationen.
- Standardmodell: qwen3:4b
- Standardadresse: http://localhost:11434
- Für Ollama ist kein API-Schlüssel erforderlich.
- Die KI-Einstellungen erklären klar den Unterschied zwischen lokaler und Cloud-KI.
- Ein fertiger "ollama pull"-Befehl kann aus dem Dialog kopiert werden.
- Der Verbindungstest prüft zuerst, ob Ollama erreichbar und das Modell installiert ist.
- Verständliche Fehlermeldung mit dem erforderlichen Installationsbefehl bei fehlendem Modell.
- OpenAI bleibt optional verfügbar.
- Unbekannte Provider werden nicht mehr stillschweigend als OpenAI behandelt.

Einrichtung auf einem Arbeitsplatz
----------------------------------
1. Ollama für Windows installieren.
2. In einer Eingabeaufforderung ausführen:

   ollama pull qwen3:4b

3. LeipzigerFlow öffnen.
4. KI -> KI-Einstellungen.
5. Anbieter "Ollama – lokal und kostenlos" auswählen.
6. Verbindung testen, KI aktivieren und speichern.

Hinweis zur späteren EXE/Setup-Datei
------------------------------------
Ollama und das mehrere Gigabyte große Modell werden nicht direkt in die
LeipzigerFlow-Programmdatei eingebettet. Der spätere Windows-Installer prüft,
ob Ollama vorhanden ist, installiert es bei Bedarf und lädt das Modell.
Für die Mitarbeitenden bleibt dies dennoch ein einheitlicher Setup-Ablauf.
