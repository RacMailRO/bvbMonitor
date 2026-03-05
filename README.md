# BVB Monitor

![BVB Monitor App](BvbMonitor.png)
![BVB Monitor Dark Mode](BvbMonitor-dark.png)

Aceasta este o aplicație asistent / widget desktop pentru monitorizarea bursei de valori (BVB) din România. Ea extrage și afișează intraday cele mai recente prețuri, variații și grafice tip „sparkline” ale celor mai tranzacționate acțiuni și ETF-uri, plus informații despre principalii indici bursieri (inclusiv evidențierea companiilor din componența indicelui BET).

## Caracteristici
- **Mod Întunecat (Dark Mode)**: Comutare manuală între teme (Dark/Light) și detecție automată a temei Windows, inclusiv bara de titlu neagră pentru un aspect premium.
- **Animații Fluide**: Evidențierea rândurilor actualizate cu un efect de „solid-hold” urmat de un „fade” lin (estompare treptată).
- **Tooltip Plutitor Inteligent**: Graficele din tabel și fereastra de detalii oferă informații precise prin tooltips care urmăresc cursorul mouse-ului.
- **Grafic Detaliat**: Click pe graficul unui simbol pentru a deschide o fereastră mare cu evoluția intraday completă, crosshair și detalii exacte.
- **Integrare BVB**: Evidențiază componentele indicelui BET (cu „*”) și oferă link-uri directe către site-ul BVB pentru fiecare simbol.
- **Acuratețe**: Extrage prețurile în timp real (acțiuni, indici, ETF-uri) și calculează variațiile intraday față de prețul de referință.
- **Auto-Update**: Detectează modificările aduse scriptului și își actualizează automat versiunea internă afișată în titlul ferestrei.
- **Istoric Intraday**: Salvează automat istoricul prețurilor pentru ziua curentă în fișiere JSON, permițând refacerea graficelor la repornire.

## Cerințe
- Python 3
- Conexiune la Internet

## Descărcare Executabil (Metoda Recomandată)
Cea mai simplă metodă de a rula aplicația, fără a instala Python sau alte dependențe, este să descarci ultima versiune gata compilată (`.exe`) direct din secțiunea [Releases](https://github.com/RacMailRO/bvbMonitor/releases).

## Instalare (Din surse / Pentru dezvoltatori)

1. Asigură-te că ai instalat Python: [https://www.python.org/downloads/](https://www.python.org/downloads/)
2. Clonează repository-ul local și accesează folderul:
   ```bash
   git clone https://github.com/RacMailRO/bvbMonitor.git
   cd bvbMonitor
   ```
3. Instalează pachetele necesare rulând:
   ```bash
   pip install -r requirements.txt
   ```
   *(Pachetele includ `pandas`, `requests`, `matplotlib`, `lxml` și `pyinstaller`. Pachetul `tkinter` este responsabil de interfața grafică desktop; acesta e inclus automat în versiunile de Python din Windows.)*

### Generare Executabil
Pentru a genera o nouă versiune `.exe` (de exemplu după ce faci modificări), pur și simplu dă dublu-click pe:
`rebuild.bat` (sau rulează `rebuild.ps1` pe sisteme mai noi).

Acesta va curăța fișierele vechi, va actualiza bibliotecile și va crea noul executabil în folderul destinație.

Datele descărcate intraday sunt salvate și pot fi consultate sau șterse la nevoie în fișiere de forma `.json` în folderul intern `data`.
