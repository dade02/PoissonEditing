from PIL import Image
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--target", required=True)
parser.add_argument("--output", default="source_resized.png")

args = parser.parse_args()

source = Image.open(args.source).convert("RGBA")
target = Image.open(args.target)

tw, th = target.size
sw, sh = source.size

# Canvas con le dimensioni del target
result = Image.new("RGBA", (tw, th), (0, 0, 0, 0))

# Posiziona la source al centro senza riscalarla
x = (tw - sw) // 2
y = (th - sh) // 2

result.paste(source, (x, y), source)

result.save(args.output)

print(f"Source: {source.size}")
print(f"Target: {target.size}")
print(f"Output: {result.size}")