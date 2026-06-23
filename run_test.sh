#!/usr/bin/env bash
# run_test.sh
# Esegue le specifiche operazioni di Poisson Image Editing basandosi sul nome 
# della cartella contenitore (tecnica) presente in data/
# I risultati vengono salvati in results/<technique>/<test_name>/

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"
PYTHON="$SCRIPT_DIR/venv/bin/python"
POISSON_SCRIPT="$SCRIPT_DIR/poisson_guided_interpolation.py"
RESULTS_DIR="$SCRIPT_DIR/results"

# Argomento da riga di comando per selezionare cosa eseguire
TARGET_TEST="${1:-all}"
# normalizza a lower case e sostituisce spazi con underscore per comodità
TARGET_TEST=$(echo "$TARGET_TEST" | tr '[:upper:]' '[:lower:]' | tr ' ' '_')

# Controlla che lo script Python esista
if [[ ! -f "$POISSON_SCRIPT" ]]; then
    echo "ERRORE: $POISSON_SCRIPT non trovato."
    exit 1
fi

# Usa il python del venv se esiste, altrimenti python3 di sistema
if [[ ! -f "$PYTHON" ]]; then
    PYTHON="python3"
fi

echo "==========================================="
echo "  Poisson Image Editing - Batch Test"
echo "==========================================="
echo "Script   : $POISSON_SCRIPT"
echo "Python   : $PYTHON"
echo "Data dir : $DATA_DIR"
echo "Results  : $RESULTS_DIR"
echo "Target   : $TARGET_TEST"
echo "==========================================="

success=0
fail=0

declare -A TECHNIQUE_MAP=(
    ["local_color_changes"]="color"
    ["local_illumination_changes"]="illumination"
    ["seamless_cloning_and_mixed_gradient"]="cloning_mixed"
    ["seamless_tiling"]="tiling"
    ["texture_flattering"]="flattening"
)

# Itera sulle cartelle delle tecniche
for tech_dir in "$DATA_DIR"/*/; do
    [[ -d "$tech_dir" ]] || continue
    tech_name=$(basename "$tech_dir")
    
    # Controlla se la cartella appartiene a una delle tecniche specificate
    tech_type="${TECHNIQUE_MAP[$tech_name]}"
    if [[ -z "$tech_type" ]]; then
        continue
    fi

    # Filtra in base all'argomento
    if [[ "$TARGET_TEST" != "all" ]]; then
        if [[ "$TARGET_TEST" == *"color"* && "$tech_type" != "color" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"illumination"* && "$tech_type" != "illumination" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"cloning"* && "$tech_type" != "cloning_mixed" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"mixed"* && "$tech_type" != "cloning_mixed" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"tiling"* && "$tech_type" != "tiling" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"flatten"* && "$tech_type" != "flattening" ]]; then continue; fi
        
        # Gestione esplicita di argomenti esatti
        if [[ "$TARGET_TEST" == "local_color_change" && "$tech_type" != "color" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "local_illumination_change" && "$tech_type" != "illumination" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "seamless_tiling" && "$tech_type" != "tiling" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "texture_flattening" && "$tech_type" != "flattening" ]]; then continue; fi
    fi

    # Itera sui test (es. test1, test2) dentro la cartella della tecnica
    for test_dir in "$tech_dir"*/; do
        [[ -d "$test_dir" ]] || continue
        test_name=$(basename "$test_dir")
        
        # Trova source (png o jpg)
        source_file=""
        for f in "$test_dir"source.png "$test_dir"source.jpg "$test_dir"source.jpeg; do
            [[ -f "$f" ]] && source_file="$f" && break
        done

        # Trova target
        target_file=""
        for f in "$test_dir"target.png "$test_dir"target.jpg "$test_dir"target.jpeg; do
            [[ -f "$f" ]] && target_file="$f" && break
        done

        # Trova mask
        mask_file=""
        for f in "$test_dir"mask.png "$test_dir"mask.jpg "$test_dir"mask.jpeg; do
            [[ -f "$f" ]] && mask_file="$f" && break
        done

        # Crea directory di output dedicata
        out_dir="${RESULTS_DIR}/${tech_name}/${test_name}"
        mkdir -p "$out_dir"

        echo ""
        echo "========================================================================"
        echo "► Elaborazione: $tech_name / $test_name"
        [[ -n "$source_file" ]] && echo "  Source: $source_file"
        [[ -n "$target_file" ]] && echo "  Target: $target_file"
        [[ -n "$mask_file" ]]   && echo "  Mask:   $mask_file"
        echo "  Output: $out_dir/"
        echo "========================================================================"

        if [[ "$tech_type" == "color" ]]; then
            if [[ -n "$source_file" && -n "$mask_file" ]]; then
                echo "--- LOCAL COLOR CHANGE ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" --mode local_color_change --output "${out_dir}/result_color_change.png"; then
                    echo "✓ Local Color Change completato"
                    ((success++)) || true
                else
                    echo "✗ Local Color Change FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Local Color Change (serve source e mask) - saltato."
            fi
            
        elif [[ "$tech_type" == "illumination" ]]; then
            if [[ -n "$source_file" && -n "$mask_file" ]]; then
                echo "--- LOCAL ILLUMINATION CHANGE ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" --mode local_illumination_change --output "${out_dir}/result_illumination.png"; then
                    echo "✓ Local Illumination Change completato"
                    ((success++)) || true
                else
                    echo "✗ Local Illumination Change FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Local Illumination Change (serve source e mask) - saltato."
            fi

        elif [[ "$tech_type" == "cloning_mixed" ]]; then
            if [[ -n "$source_file" && -n "$target_file" && -n "$mask_file" ]]; then
                echo "--- SEAMLESS CLONING ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_file" --mode seamless_cloning --output "${out_dir}/result_cloning.png"; then
                    echo "✓ Seamless Cloning completato"
                    ((success++)) || true
                else
                    echo "✗ Seamless Cloning FALLITO"
                    ((fail++)) || true
                fi

                echo "--- MIXED GRADIENT CLONING ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_file" --mode mixed_gradient --output "${out_dir}/result_mixed.png"; then
                    echo "✓ Mixed Gradient Cloning completato"
                    ((success++)) || true
                else
                    echo "✗ Mixed Gradient Cloning FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Cloning/Mixed (serve source, target e mask) - saltato."
            fi

        elif [[ "$tech_type" == "tiling" ]]; then
            if [[ -n "$source_file" ]]; then
                echo "--- SEAMLESS TILING ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" --mode seamless_tiling --output "${out_dir}/result_tiling.png"; then
                    echo "✓ Seamless Tiling completato"
                    ((success++)) || true
                else
                    echo "✗ Seamless Tiling FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Seamless Tiling (serve source) - saltato."
            fi

        elif [[ "$tech_type" == "flattening" ]]; then
            if [[ -n "$target_file" && -n "$mask_file" ]]; then
                echo "--- TEXTURE FLATTENING ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$target_file" "$mask_file" --mode texture_flattening --output "${out_dir}/result_flattening.png"; then
                    echo "✓ Texture Flattening completato"
                    ((success++)) || true
                else
                    echo "✗ Texture Flattening FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Texture Flattening (serve target e mask) - saltato."
            fi
        fi

    done
done

echo ""
echo "========================================================================"
echo "  Esecuzione completata: $success operazioni ok, $fail fallite"
echo "========================================================================"
