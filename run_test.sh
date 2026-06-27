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
            if [[ "$test_name" == "test0" ]]; then
                # ---------- CASO SPECIALE: test0 (3 step sequenziali con source1/source2 e mask_source/mask_target specifiche) ----------
                source1_file=$(find_file "source1" "$test_dir") || source1_file=""
                source2_file=$(find_file "source2" "$test_dir") || source2_file=""

                mask_source1=""
                mask_target1=""
                mask_source2=""
                mask_target2=""
                mask_source3=""
                mask_target3=""

                for ext in png jpg jpeg; do
                    if [[ -f "${test_dir}mask_source1.${ext}" ]]; then
                        mask_source1="${test_dir}mask_source1.${ext}"
                    fi
                    if [[ -f "${test_dir}mask_target1.${ext}" ]]; then
                        mask_target1="${test_dir}mask_target1.${ext}"
                    fi
                    if [[ -f "${test_dir}mask_source2.${ext}" ]]; then
                        mask_source2="${test_dir}mask_source2.${ext}"
                    fi
                    if [[ -f "${test_dir}mask_target2.${ext}" ]]; then
                        mask_target2="${test_dir}mask_target2.${ext}"
                    fi
                    if [[ -f "${test_dir}mask_source3.${ext}" ]]; then
                        mask_source3="${test_dir}mask_source3.${ext}"
                    fi
                    if [[ -f "${test_dir}mask_target3.${ext}" ]]; then
                        mask_target3="${test_dir}mask_target3.${ext}"
                    fi
                done

                echo "  Target:  $target_file"
                [[ -n "$source1_file" ]] && echo "  Source1: $(basename "$source1_file")"
                [[ -n "$source2_file" ]] && echo "  Source2: $(basename "$source2_file")"
                [[ -n "$mask_source1" ]] && echo "  Mask Source1: $(basename "$mask_source1")"
                [[ -n "$mask_target1" ]] && echo "  Mask Target1: $(basename "$mask_target1")"
                [[ -n "$mask_source2" ]] && echo "  Mask Source2: $(basename "$mask_source2")"
                [[ -n "$mask_target2" ]] && echo "  Mask Target2: $(basename "$mask_target2")"
                [[ -n "$mask_source3" ]] && echo "  Mask Source3: $(basename "$mask_source3")"
                [[ -n "$mask_target3" ]] && echo "  Mask Target3: $(basename "$mask_target3")"

                if [[ -z "$target_file" || -z "$source1_file" || -z "$source2_file" || -z "$mask_source1" || -z "$mask_target1" || -z "$mask_source2" || -z "$mask_target2" || -z "$mask_source3" || -z "$mask_target3" ]]; then
                    echo "⚠ File mancanti per test0 - serve:"
                    echo "    source1, source2, target"
                    echo "    mask_source1, mask_target1, mask_source2, mask_target2, mask_source3, mask_target3"
                    echo "  Saltato."
                else
                    echo "--- TEST0: Seamless Cloning sequenziale 3 step ---"
                    current_target="$target_file"
                    success_cloning=true

                    step1_output="${out_dir}/prodotto.png"
                    step2_output="${out_dir}/prodotto2.png"
                    final_output="${out_dir}/prodotto_finale.png"

                    echo "  -> Step 1: source1 + mask_source1/mask_target1 -> prodotto"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source1_file" "$current_target" "$mask_target1" \
                        --mask-source "$mask_source1" --mask-target "$mask_target1" \
                        --mode seamless_cloning --output "$step1_output"; then
                        current_target="${step1_output%.png}_cloning.png"
                        echo "    ✓ Step 1 completato"
                    else
                        echo "    ✗ Step 1 FALLITO"
                        success_cloning=false
                    fi

                    if [[ "$success_cloning" == "true" ]]; then
                        echo "  -> Step 2: source2 + mask_source2/mask_target2 -> prodotto2"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "$current_target" "$mask_target2" \
                            --mask-source "$mask_source2" --mask-target "$mask_target2" \
                            --mode seamless_cloning --output "$step2_output"; then
                            current_target="${step2_output%.png}_cloning.png"
                            echo "    ✓ Step 2 completato"
                        else
                            echo "    ✗ Step 2 FALLITO"
                            success_cloning=false
                        fi
                    fi

                    if [[ "$success_cloning" == "true" ]]; then
                        echo "  -> Step 3: source2 + mask_source3/mask_target3 -> prodotto_finale"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "$current_target" "$mask_target3" \
                            --mask-source "$mask_source3" --mask-target "$mask_target3" \
                            --mode seamless_cloning --output "$final_output"; then
                            current_target="$final_output"
                            echo "    ✓ Step 3 completato"
                        else
                            echo "    ✗ Step 3 FALLITO"
                            success_cloning=false
                        fi
                    fi

                    if [[ "$success_cloning" == "true" ]]; then
                        echo "✓ Seamless Cloning sequenziale completato: risultato finale -> $final_output"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning sequenziale FALLITO"
                        ((fail++)) || true
                    fi

                    echo "--- TEST0: Mixed Gradient sequenziale 3 step ---"
                    current_target="$target_file"
                    success_mixed=true

                    step1_mixed_output="${out_dir}/prodotto_mixed.png"
                    step2_mixed_output="${out_dir}/prodotto2_mixed.png"
                    final_mixed_output="${out_dir}/prodotto_finale_mixed.png"

                    echo "  -> Step 1: source1 + mask_source1/mask_target1 -> prodotto_mixed"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source1_file" "$current_target" "$mask_target1" \
                        --mask-source "$mask_source1" --mask-target "$mask_target1" \
                        --mode mixed_gradient --output "$step1_mixed_output"; then
                        current_target="${step1_mixed_output%.png}_mixed.png"
                        echo "    ✓ Step 1 completato"
                    else
                        echo "    ✗ Step 1 FALLITO"
                        success_mixed=false
                    fi

                    if [[ "$success_mixed" == "true" ]]; then
                        echo "  -> Step 2: source2 + mask_source2/mask_target2 -> prodotto2_mixed"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "$current_target" "$mask_target2" \
                            --mask-source "$mask_source2" --mask-target "$mask_target2" \
                            --mode mixed_gradient --output "$step2_mixed_output"; then
                            current_target="${step2_mixed_output%.png}_mixed.png"
                            echo "    ✓ Step 2 completato"
                        else
                            echo "    ✗ Step 2 FALLITO"
                            success_mixed=false
                        fi
                    fi

                    if [[ "$success_mixed" == "true" ]]; then
                        echo "  -> Step 3: source2 + mask_source3/mask_target3 -> prodotto_finale_mixed"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source2_file" "$current_target" "$mask_target3" \
                            --mask-source "$mask_source3" --mask-target "$mask_target3" \
                            --mode mixed_gradient --output "$final_mixed_output"; then
                            current_target="$final_mixed_output"
                            echo "    ✓ Step 3 completato"
                        else
                            echo "    ✗ Step 3 FALLITO"
                            success_mixed=false
                        fi
                    fi

                    if [[ "$success_mixed" == "true" ]]; then
                        echo "✓ Mixed Gradient sequenziale completato: risultato finale -> $final_mixed_output"
                        ((success++)) || true
                    else
                        echo "✗ Mixed Gradient sequenziale FALLITO"
                        ((fail++)) || true
                    fi
                fi
            elif [[ "$test_name" == "test9" ]]; then
                # ---------- CASO SPECIALE: test9 (texture swapping con mask_sourceN/mask_targetN sequenziali) ----------
                source_masks=()
                target_masks=()
                idx=1

                while true; do
                    src_found=""
                    tgt_found=""

                    for ext in png jpg jpeg; do
                        if [[ -f "${test_dir}mask_source${idx}.${ext}" ]]; then
                            src_found="${test_dir}mask_source${idx}.${ext}"
                            break
                        fi
                    done
                    for ext in png jpg jpeg; do
                        if [[ -f "${test_dir}mask_target${idx}.${ext}" ]]; then
                            tgt_found="${test_dir}mask_target${idx}.${ext}"
                            break
                        fi
                    done

                    if [[ -z "$src_found" && -z "$tgt_found" ]]; then
                        break
                    fi

                    if [[ -z "$src_found" || -z "$tgt_found" ]]; then
                        echo "⚠ Mancano mask_source${idx} o mask_target${idx} in $test_name - saltato."
                        source_masks=()
                        target_masks=()
                        break
                    fi

                    source_masks+=("$src_found")
                    target_masks+=("$tgt_found")
                    ((idx++))
                done

                if [[ -n "$source_file" && -n "$target_file" && ${#target_masks[@]} -gt 0 ]]; then
                    echo "--- TEST9: Seamless Cloning sequenziale ---"
                    current_target="$target_file"
                    success_cloning=true

                    for ((i=0; i<${#target_masks[@]}; i++)); do
                        step_output="${out_dir}/result_cloning_step$((i+1)).png"
                        src_mask="${source_masks[i]}"
                        tgt_mask="${target_masks[i]}"

                        echo "  -> Step $((i+1)) / ${#target_masks[@]} (seamless) con source: $(basename "$src_mask") target: $(basename "$tgt_mask")"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$current_target" "$tgt_mask" \
                            --mask-source "$src_mask" --mask-target "$tgt_mask" \
                            --mode seamless_cloning --output "$step_output"; then
                            current_target="${step_output%.png}_cloning.png"
                        else
                            echo "  ✗ Step $((i+1)) (seamless) FALLITO"
                            success_cloning=false
                            break
                        fi

                        src_mask="${target_masks[i]}"
                        tgt_mask="${source_masks[i]}"
                        echo "  -> Step $((i+1)) / ${#target_masks[@]} (seamless) con source: $(basename "$src_mask") target: $(basename "$tgt_mask")"
                        if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$current_target" "$tgt_mask" \
                            --mask-source "$src_mask" --mask-target "$tgt_mask" \
                            --mode seamless_cloning --output "$step_output"; then
                            current_target="${step_output%.png}_cloning.png"
                        else
                            echo "  ✗ Step $((i+1)) (seamless) FALLITO"
                            success_cloning=false
                            break
                        fi


                        
                    done

                    if [[ "$success_cloning" == "true" ]]; then
                        echo "✓ Seamless Cloning sequenziale completato: risultato finale -> $current_target"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning sequenziale FALLITO"
                        ((fail++)) || true
                    fi

                   
                else
                    echo "⚠ File mancanti per test9 (serve source, target e almeno una coppia mask_sourceN/mask_targetN) - saltato."
                fi
            elif [[ "$test_name" == "test-1" ]]; then
                # ---------- CASO SPECIALE: test-1 (texture transfer con mask_source e mask_target singole, con e senza monochrome transfer) ----------
                mask_source_file=""
                mask_target_file=""

                for ext in png jpg jpeg; do
                    if [[ -f "${test_dir}mask_source.${ext}" ]]; then
                        mask_source_file="${test_dir}mask_source.${ext}"
                        break
                    fi
                done
                for ext in png jpg jpeg; do
                    if [[ -f "${test_dir}mask_target.${ext}" ]]; then
                        mask_target_file="${test_dir}mask_target.${ext}"
                        break
                    fi
                done

                if [[ -n "$source_file" && -n "$target_file" && -n "$mask_source_file" && -n "$mask_target_file" ]]; then
                    # ==== VERSIONE STANDARD (senza monochrome transfer) ====
                    echo "--- TEST-1: Seamless Cloning (standard) ---"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_target_file" \
                        --mask-source "$mask_source_file" --mask-target "$mask_target_file" \
                        --mode seamless_cloning --output "${out_dir}/result_cloning.png"; then
                        echo "✓ Seamless Cloning (standard) completato"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning (standard) FALLITO"
                        ((fail++)) || true
                    fi

                    

                    # ==== VERSIONE CON MONOCHROME TRANSFER ====
                    echo "--- TEST-1: Seamless Cloning (monochrome transfer) ---"
                    if "$PYTHON" "$POISSON_SCRIPT" "$source_file" "$target_file" "$mask_target_file" \
                        --mask-source "$mask_source_file" --mask-target "$mask_target_file" \
                        --mode seamless_cloning --monochrome-transfer --output "${out_dir}/result_cloning_mono.png"; then
                        echo "✓ Seamless Cloning (monochrome transfer) completato"
                        ((success++)) || true
                    else
                        echo "✗ Seamless Cloning (monochrome transfer) FALLITO"
                        ((fail++)) || true
                    fi

                    
                else
                    echo "⚠ File mancanti per test-1 (serve source, target, mask_source e mask_target) - saltato."
                fi
            elif [[ "$test_name" == "test6" ]]; then
                # ---------- CASO SPECIALE: test6 (più maschere target in sequenza) ----------
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
                    echo "--- TEST6: Seamless Cloning (sequential) ---"
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