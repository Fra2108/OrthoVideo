# OrthoVideo

OrthoVideo genera sei viste ortogonali, una tavola tecnica europea
first-angle e un'animazione Blender da modelli STEP/STP o OBJ.

- STEP usa OpenCascade B-Rep/HLR ed è la sorgente geometrica autorevole.
- OBJ usa feature/silhouette edge e ray casting sulla mesh.
- Le centerline automatiche sono generate da cilindri STEP completi,
  consolidando facce CAD spezzate e assi coassiali.
- SVG, PDF, DXF e il fotogramma finale Blender condividono lo stesso
  orientamento first-angle.
- La tavola a sei viste usa una scala ISO intermedia quando serve (per esempio
  1:2,5) e un preset di linee alleggerito; la pagina di sezione conserva pesi
  più marcati e indipendenti.
- L'animazione usa una vera scatola di proiezione chiusa: FRONT è fisso,
  quattro facce sono incernierate ai suoi bordi e REAR è figlio di LEFT.
- Il modello animato usa materiale tecnico contrastato, cavity/AO, luce chiave,
  fill e rim light per rendere leggibili fori, raccordi e variazioni di quota.
- Le sezioni STEP tagliano davvero il B-Rep e rimuovono il semimodello davanti
  al piano; le sezioni OBJ usano il corrispondente clipping mesh. La sezione
  A-A è una vista separata (seconda pagina PDF), non una campitura sovrapposta
  a una delle sei viste ordinarie.
- L'MP4 viene codificato con FFmpeg esterno; `ffmpeg.exe` deve essere
  disponibile nel `PATH` (la build Blender 5.1.2 installata non espone
  l'output FFMPEG interno).

## Comando completo

Da PowerShell, nella cartella del progetto:

```powershell
.\.venv\Scripts\python.exe -m orthovideo .\models\componente_valvola.step `
  --normal 0 -1 0 --up 0 0 1
```

Per usare interamente `config/project.json`:

```powershell
.\.venv\Scripts\python.exe -m orthovideo
```

Per generare solo tavola e formati tecnici senza avviare Blender:

```powershell
.\.venv\Scripts\python.exe -m orthovideo .\models\test_mesh.obj --no-video
```

Una sezione e la relativa campitura possono essere selezionate da comando:

```powershell
.\.venv\Scripts\python.exe -m orthovideo .\models\componente_valvola.step `
  --normal 0 -1 0 --up 0 0 1 `
  --section-view front --section-reference-view left `
  --section-offset 0 --hatch-spacing 5
```

`--tangent-edges omit|thin|full` controlla le linee di tangenza STEP.
`--hidden` mostra tutte le linee nascoste; `--hidden-view front` (ripetibile)
le abilita soltanto nelle viste richieste, mentre `--no-hidden` le disattiva
anche se il config contiene `hidden_views`. `--pitch-circle-view bottom`
riconosce automaticamente una matrice simmetrica di quattro fori e aggiunge
circonferenza primitiva e radiali. `--no-section` disattiva la sezione.

## Convenzioni grafiche

- `VISIBLE`: continua 0,20 mm nella tavola, 0,35 mm nella sezione.
- `HIDDEN`: tratteggiata fine, 0,13/0,18 mm.
- `CENTER`, `SYMMETRY`, `PITCH`: tratto-punto fine, 0,13/0,18 mm.
- `SECTION_CUT`: contorno di sezione marcato.
- `HATCH`: continua fine a 45° nelle sole aree solide tagliate.
- `TANGENT`: continua fine, opzionale.

Nella prima pagina `VISIBLE` usa 0,20 mm e gli assi 0,13 mm. Le centro-marche
dei fori STEP sono generate solo per cerchi realmente visibili nella singola
proiezione e formano un `+` simmetrico, proporzionato al diametro del foro. Il
centro principale usa il maggiore cerchio interno visibile, evitando che gli
assi raggiungano automaticamente la sagoma esterna della flangia.

La sezione usa il solo contorno HLR come bordo visibile: la slice B-Rep fornisce
la campitura, senza ridisegnare una seconda volta gli stessi bordi. Gli assi
della sezione sono limitati ai cilindri realmente attraversati dal piano e
ritagliati sull'ingombro della vista. Nel JSON, `section_reference_view`
seleziona la vista della traccia A-A; `hidden_views` e `pitch_circle_views`
sono liste di nomi tra `front`, `rear`, `top`, `bottom`, `right`, `left`.

Gli stessi ruoli, pesi e pattern sono usati da SVG, PDF e DXF. Il DXF
contiene tabelle `LTYPE` reali e lineweight CAD. Assi di simmetria e
circonferenze primitive che non sono deducibili dalla geometria possono essere
aggiunti esplicitamente in `technical_annotations` nel JSON:

```json
{
  "view": "front",
  "role": "PITCH",
  "center": [0.0, 0.0],
  "radius": 25.0
}
```

Gli output sono scritti nella directory configurata. `orthographic_sheet.pdf`
contiene la tavola first-angle e, quando richiesta, una seconda pagina
`SEZIONE A-A`; SVG e DXF della sezione sono anche esportati separatamente come
`section_A-A.svg` e `section_A-A.dxf`. Il `manifest.json` registra sorgente,
vista principale, conteggi e percorsi.
