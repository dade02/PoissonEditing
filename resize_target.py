from PIL import Image
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("--source", required=True)
parser.add_argument("--target", required=True)
parser.add_argument("--output", default="target_resized.png")

args = parser.parse_args()

source = Image.open(args.source)
target = Image.open(args.target)

target_resized = target.resize(source.size, Image.LANCZOS)
target_resized.save(args.output)

print(f"Source: {source.size}")
print(f"Target resized: {target_resized.size}")
print(f"Saved: {args.output}")