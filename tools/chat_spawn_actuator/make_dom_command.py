#!/usr/bin/env python3
import argparse, json
from actuation_policy import encode_dom_command

ap = argparse.ArgumentParser(description="Encode a bounded Primary browser-actuation command marker")
ap.add_argument("json_file")
args = ap.parse_args()
doc = json.load(open(args.json_file, encoding="utf-8"))
print(encode_dom_command(doc))
