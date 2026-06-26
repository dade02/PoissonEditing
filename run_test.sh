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

# Helper: cerca un file con diverse estensioni
find_file() {
    local base="$1"
    local dir="$2"
    for ext in png jpg jpeg; do
        local f="${dir}${base}.${ext}"
        [[ -f "$f" ]] && echo "$f" && return 0
    done
    return 1
}

# Itera sulle cartelle delle tecniche
for tech_dir in "$DATA_DIR"/*/; do
    [[ -d "$tech_dir" ]] || continue
    tech_name=$(basename "$tech_dir")
    
    tech_type="${TECHNIQUE_MAP[$tech_name]}"
    [[ -z "$tech_type" ]] && continue

    # Filtra in base all'argomento
    if [[ "$TARGET_TEST" != "all" ]]; then
        if [[ "$TARGET_TEST" == *"color"* && "$tech_type" != "color" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"illumination"* && "$tech_type" != "illumination" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"cloning"* && "$tech_type" != "cloning_mixed" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"mixed"* && "$tech_type" != "cloning_mixed" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"tiling"* && "$tech_type" != "tiling" ]]; then continue; fi
        if [[ "$TARGET_TEST" == *"flatten"* && "$tech_type" != "flattening" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "local_color_change" && "$tech_type" != "color" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "local_illumination_change" && "$tech_type" != "illumination" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "seamless_tiling" && "$tech_type" != "tiling" ]]; then continue; fi
        if [[ "$TARGET_TEST" == "texture_flattening" && "$tech_type" != "flattening" ]]; then continue; fi
    fi

    for test_dir in "$tech_dir"*/; do
        [[ -d "$test_dir" ]] || continue
        test_name=$(basename "$test_dir")
        
        # Cerca file generici (source, target, mask)
        source_file=""
        for f in "$test_dir"source.png "$test_dir"source.jpg "$test_dir"source.jpeg; do
            [[ -f "$f" ]] && source_file="$f" && break
        done
        target_file=""
        for f in "$test_dir"target.png "$test_dir"target.jpg "$test_dir"target.jpeg; do
            [[ -f "$f" ]] && target_file="$f" && break
        done
        mask_file=""
        for f in "$test_dir"mask.png "$test_dir"mask.jpg "$test_dir"mask.jpeg; do
            [[ -f "$f" ]] && mask_file="$f" && break
        done

        # Cerca maschere specifiche (mask_source, mask_target)
        mask_source_file=""
        for f in "$test_dir"mask_source.png "$test_dir"mask_source.jpg "$test_dir"mask_source.jpeg; do
            [[ -f "$f" ]] && mask_source_file="$f" && break
        done
        mask_target_file=""
        for f in "$test_dir"mask_target.png "$test_dir"mask_target.jpg "$test_dir"mask_target.jpeg; do
            [[ -f "$f" ]] && mask_target_file="$f" && break
        done

        mask_opts=()
        if [[ -n "$mask_source_file" && -n "$mask_target_file" ]]; then
            mask_opts=(--mask-source "$mask_source_file" --mask-target "$mask_target_file")
            mask_file="$mask_target_file"
        fi

        out_dir="${RESULTS_DIR}/${tech_name}/${test_name}"
        mkdir -p "$out_dir"

        echo ""
        echo "========================================================================"
        echo "► Elaborazione: $tech_name / $test_name"
        if [[ "$test_name" == "test6" && "$tech_type" == "cloning_mixed" ]]; then
            # Stampa specifica per test6 (verrà fatta dopo aver trovato i file)
            echo "  (test6: multi‑source)"
        else
            [[ -n "$source_file" ]] && echo "  Source: $source_file"
            [[ -n "$target_file" ]] && echo "  Target: $target_file"
            if [[ -n "$mask_source_file" && -n "$mask_target_file" ]]; then
                echo "  Mask Source: $mask_source_file"
                echo "  Mask Target: $mask_target_file"
            else
                [[ -n "$mask_file" ]]   && echo "  Mask:   $mask_file"
            fi
        fi
        echo "  Output: $out_dir/"
        echo "========================================================================"

        if [[ "$tech_type" == "color" ]]; then
            # (codice invariato per color)
            if [[ -n "$source_file" && -n "$mask_file" ]]; then
                echo "--- LOCAL COLOR CHANGE (gray_background) ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" "${mask_opts[@]}" \
                    --mode local_color_change \
                    --color-mode gray_background \
                    --output "${out_dir}/result_gray_background.png"; then
                    echo "✓ gray_background completato"
                    ((success++)) || true
                else
                    echo "✗ gray_background FALLITO"
                    ((fail++)) || true
                fi

                echo "--- LOCAL COLOR CHANGE (multiply_rgb) ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" "${mask_opts[@]}" \
                    --mode local_color_change \
                    --color-mode multiply_rgb \
                    --rgb-factors 1.5 0.5 0.5 \
                    --output "${out_dir}/result_multiply_rgb.png"; then
                    echo "✓ multiply_rgb completato"
                    ((success++)) || true
                else
                    echo "✗ multiply_rgb FALLITO"
                    ((fail++)) || true
                fi

                echo "--- LOCAL COLOR CHANGE (color_change - hue shifts) ---"
                for hue in 60 120 180 240; do
                    if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" "${mask_opts[@]}" \
                        --mode local_color_change \
                        --color-mode color_change \
                        --change-hue "$hue" \
                        --output "${out_dir}/result_color_change_hue${hue}.png"; then
                        echo "✓ color_change (hue=${hue}) completato"
                        ((success++)) || true
                    else
                        echo "✗ color_change (hue=${hue}) FALLITO"
                        ((fail++)) || true
                    fi
                done
            else
                echo "⚠ File mancanti per Local Color Change (serve source e mask) - saltato."
            fi

        elif [[ "$tech_type" == "illumination" ]]; then
            if [[ -n "$source_file" && -n "$mask_file" ]]; then
                echo "--- LOCAL ILLUMINATION CHANGE ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" "${mask_opts[@]}" \
                    --mode local_illumination_change \
                    --output "${out_dir}/result_illumination.png"; then
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
            if [[ "$test_name" == "test6" ]]; then
                # ---------- CASO SPECIALE: test6 (due source + due mask) ----------
                source1_file=$(find_file "source1" "$test_dir")
                mask1_file=$(find_file "mask1" "$test_dir")
                source2_file=$(find_file "source2" "$test_dir")
                mask2_file=$(find_file "mask2" "$test_dir")
                # target_file già disponibile

                echo "  Source1: $source1_file"
                echo "  Mask1:   $mask1_file"
                echo "  Source2: $source2_file"
                echo "  Mask2:   $mask2_file"
                echo "  Target:  $target_file"

                if [[ -n "$source1_file" && -n "$mask1_file" && -n "$source2_file" && -n "$mask2_file" && -n "$target_file" ]]; then
                    echo "--- TEST6: Seamless Cloning (two-step) ---"
                    intermediate="${out_dir}/intermediate_cloning.png"
                    final="${out_dir}/result_cloning.png"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source1_file" "$target_file" "$mask1_file" \
                        --mode seamless_cloning  --output "$intermediate"; then
                        echo "  ✓ Primo step (seamless) completato"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "${intermediate%.png}_cloning.png" "$mask2_file" \
                            --mode seamless_cloning --output "$final"; then
                            echo "  ✓ Secondo step (seamless) completato → ${final}"
                            ((success++)) || true
                        else
                            echo "  ✗ Secondo step (seamless) FALLITO"
                            ((fail++)) || true
                        fi
                    else
                        echo "  ✗ Primo step (seamless) FALLITO"
                        ((fail++)) || true
                    fi

                    echo "--- TEST6: Mixed Gradient Cloning (two-step) ---"
                    intermediate="${out_dir}/intermediate_mixed.png"
                    final="${out_dir}/result_mixed.png"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source1_file" "$target_file" "$mask1_file" \
                        --mode mixed_gradient --output "$intermediate"; then
                        echo "  ✓ Primo step (mixed) completato"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "${intermediate%.png}_mixed.png" "$mask2_file" \
                            --mode mixed_gradient --output "$final"; then
                            echo "  ✓ Secondo step (mixed) completato → ${final}"
                            ((success++)) || true
                        else
                            echo "  ✗ Secondo step (mixed) FALLITO"
                            ((fail++)) || true
                        fi
                    else
                        echo "  ✗ Primo step (mixed) FALLITO"
                        ((fail++)) || true
                    fi
                else
                    echo "⚠ File mancanti per test6 (servono source1, mask1, source2, mask2, target) - saltato."
                fi
            elif [[ "$test_name" == "test0" ]]; then
                # ---------- CASO SPECIALE: test0 (più maschere target in sequenza) ----------
                target_masks=()
                source_masks=()
                
                # Primo step: mask_source e mask_target
                src1=""
                for ext in png jpg jpeg; do
                    if [[ -f "${test_dir}mask_source.${ext}" ]]; then
                        src1="${test_dir}mask_source.${ext}"
                        break
                    fi
                done
                tgt1=""
                for ext in png jpg jpeg; do
                    if [[ -f "${test_dir}mask_target.${ext}" ]]; then
                        tgt1="${test_dir}mask_target.${ext}"
                        break
                    fi
                done
                
                if [[ -n "$tgt1" ]]; then
                    target_masks+=("$tgt1")
                    source_masks+=("$src1")
                fi
                
                # Step successivi
                idx=2
                while true; do
                    tgt_found=""
                    for ext in png jpg jpeg; do
                        if [[ -f "${test_dir}mask_target${idx}.${ext}" ]]; then
                            tgt_found="${test_dir}mask_target${idx}.${ext}"
                            break
                        fi
                    done
                    if [[ -z "$tgt_found" ]]; then
                        break
                    fi
                    
                    src_found=""
                    for ext in png jpg jpeg; do
                        if [[ -f "${test_dir}mask_source${idx}.${ext}" ]]; then
                            src_found="${test_dir}mask_source${idx}.${ext}"
                            break
                        fi
                    done
                    if [[ -z "$src_found" ]]; then
                        src_found="$src1"
                    fi
                    
                    target_masks+=("$tgt_found")
                    source_masks+=("$src_found")
                    ((idx++))
                done

                if [[ -n "$source_file" && -n "$target_file" && ${#target_masks[@]} -gt 0 ]]; then
                    # --- SEAMLESS CLONING SEQUENZIALE ---
                    echo "--- TEST0: Seamless Cloning (sequential) ---"
                    current_target="$target_file"
                    success_cloning=true
                    
                    for ((i=0; i<${#target_masks[@]}; i++)); do
                        tgt_mask="${target_masks[i]}"
                        src_mask="${source_masks[i]}"
                        
                        if (( i == ${#target_masks[@]} - 1 )); then
                            step_output="${out_dir}/result_cloning.png"
                            expected_out="${out_dir}/result_cloning_cloning.png"
                        else
                            step_output="${out_dir}/intermediate_cloning_$((i+1)).png"
                            expected_out="${out_dir}/intermediate_cloning_$((i+1))_cloning.png"
                        fi
                        
                        opts=()
                        if [[ -n "$src_mask" ]]; then
                            opts=(--mask-source "$src_mask" --mask-target "$tgt_mask")
                        fi
                        
                        echo "  -> Step $((i+1)) / ${#target_masks[@]} (seamless) con target mask: $(basename "$tgt_mask")"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$current_target" "$tgt_mask" "${opts[@]}" \
                            --mode seamless_cloning --output "$step_output"; then
                            current_target="$expected_out"
                        else
                            echo "  ✗ Step $((i+1)) (seamless) FALLITO"
                            success_cloning=false
                            break
                        fi
                    done
                    
                    if [[ "$success_cloning" == "true" ]]; then
                        echo "✓ Seamless Cloning sequenziale completato"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning sequenziale FALLITO"
                        ((fail++)) || true
                    fi
                else
                    echo "⚠ File mancanti o nessuna maschera target per test0 - saltato."
                fi
            else
                # ---------- CASO STANDARD per tutti gli altri test ----------
                if [[ -n "$source_file" && -n "$target_file" && -n "$mask_file" ]]; then
                    echo "--- SEAMLESS CLONING ---"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_file" "${mask_opts[@]}" \
                        --mode seamless_cloning --output "${out_dir}/result_cloning.png"; then
                        echo "✓ Seamless Cloning completato"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning FALLITO"
                        ((fail++)) || true
                    fi

                    echo "--- MIXED GRADIENT CLONING ---"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_file" "${mask_opts[@]}" \
                        --mode mixed_gradient --output "${out_dir}/result_mixed.png"; then
                        echo "✓ Mixed Gradient Cloning completato"
                        ((success++)) || true
                    else
                        echo "✗ Mixed Gradient Cloning FALLITO"
                        ((fail++)) || true
                    fi
                else
                    echo "⚠ File mancanti per Cloning/Mixed (serve source, target e mask) - saltato."
                fi
            fi

        elif [[ "$tech_type" == "tiling" ]]; then
            if [[ -n "$source_file" ]]; then
                echo "--- SEAMLESS TILING ---"
                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" --mode seamless_tiling \
                    --output "${out_dir}/result_tiling.png"; then
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
            if [[ -n "$source_file" && -n "$mask_file" ]]; then
                echo "--- TEXTURE FLATTENING ---"
                edge_opt=""
                edge_file=""
                for f in "$test_dir"edge.png "$test_dir"edge.jpg "$test_dir"edge.jpeg; do
                    [[ -f "$f" ]] && edge_file="$f" && break
                done
                [[ -n "$edge_file" ]] && edge_opt="--edge-image $edge_file"

                if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$mask_file" "${mask_opts[@]}" \
                    --mode texture_flattening $edge_opt \
                    --output "${out_dir}/result_flattening.png"; then
                    echo "✓ Texture Flattening completato"
                    ((success++)) || true
                else
                    echo "✗ Texture Flattening FALLITO"
                    ((fail++)) || true
                fi
            else
                echo "⚠ File mancanti per Texture Flattening (serve source e mask) - saltato."
            fi
        fi

    done
done

echo ""
echo "========================================================================"
echo "  Esecuzione completata: $success operazioni ok, $fail fallite"
echo "========================================================================"