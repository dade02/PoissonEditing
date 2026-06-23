#!/usr/bin/env bash
# run_seamless_and_mixed.sh
# Esegue seamless cloning e mixed gradient per ogni test in data/seamless_cloning_and_mixed_gradient

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data/seamless_cloning_and_mixed_gradient"
PYTHON="$SCRIPT_DIR/venv/bin/python"
POISSON_SCRIPT="$SCRIPT_DIR/poisson_guided_interpolation.py"
RESULTS_DIR="$SCRIPT_DIR/results/seamless_cloning_and_mixed_gradient"

# Controlla che la cartella data esista
if [[ ! -d "$DATA_DIR" ]]; then
    echo "ERRORE: $DATA_DIR non trovato."
    exit 1
fi

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
echo "  Seamless Cloning & Mixed Gradient Batch"
echo "==========================================="
echo "Script   : $POISSON_SCRIPT"
echo "Python   : $PYTHON"
echo "Data dir : $DATA_DIR"
echo "Results  : $RESULTS_DIR"
echo "==========================================="

# Crea la directory di risultati principale
mkdir -p "$RESULTS_DIR"

success=0
fail=0

# Itera su ogni test
for test_dir in "$DATA_DIR"/test*/; do
    [[ -d "$test_dir" ]] || continue

    name=$(basename "$test_dir")

    # Cerca i file richiesti (source, target, mask)
    source_file=""
    target_file=""
    mask_file=""

    for f in "$test_dir"source.{png,jpg,jpeg}; do
        [[ -f "$f" ]] && source_file="$f" && break
    done

    for f in "$test_dir"target.{png,jpg,jpeg}; do
        [[ -f "$f" ]] && target_file="$f" && break
    done

    for f in "$test_dir"mask.{png,jpg,jpeg}; do
        [[ -f "$f" ]] && mask_file="$f" && break
    done

    # Controlla se tutti i file necessari sono presenti
    if [[ -z "$source_file" || -z "$target_file" || -z "$mask_file" ]]; then
        echo ""
        echo "⚠  $name: file mancanti (source, target o mask) — saltato."
        echo "   Found: source=$source_file, target=$target_file, mask=$mask_file"
        ((fail++)) || true
        continue
    fi

    # Crea directory di output dedicata
    out_dir="${RESULTS_DIR}/${name}"
    mkdir -p "$out_dir"

    echo ""
    echo "========================================================================"
    echo "► Elaborazione: $name"
    echo "  Source: $(basename "$source_file")"
    echo "  Target: $(basename "$target_file")"
    echo "  Mask:   $(basename "$mask_file")"
    echo "  Output: $out_dir/"
    echo "========================================================================"

    # 1. SEAMLESS CLONING
    echo "--- [1/2] SEAMLESS CLONING ---"
    if "$PYTHON" "$POISSON_SCRIPT" \
            "$source_file" "$target_file" "$mask_file" \
            --mode seamless_cloning \
            --colorspace RGB \
            --output "${out_dir}/seamless_cloning.png"; then
        echo "✓ Seamless Cloning completato"
        ((success++)) || true
    else
        echo "✗ Seamless Cloning FALLITO"
        ((fail++)) || true
    fi

    # 2. MIXED GRADIENT
    echo "--- [2/2] MIXED GRADIENT CLONING ---"
    if "$PYTHON" "$POISSON_SCRIPT" \
            "$source_file" "$target_file" "$mask_file" \
            --mode mixed_gradient \
            --colorspace RGB \
            --output "${out_dir}/mixed_gradient.png"; then
        echo "✓ Mixed Gradient completato"
        ((success++)) || true
    else
        echo "✗ Mixed Gradient FALLITO"
        ((fail++)) || true
    fi

done

echo ""
echo "==========================================="
echo "  Riepilogo"
echo "==========================================="
echo "✓ Completati: $success"
echo "✗ Falliti: $fail"
echo "Results in: $RESULTS_DIR"
echo "==========================================="

if [[ $fail -gt 0 ]]; then
    exit 1
fi

exit 0
