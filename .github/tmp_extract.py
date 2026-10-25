import re, sys
t = open(sys.argv[1]).read()
lines = [l for l in t.splitlines() if re.search(r"(Error|assert |Exception|FAIL:)", l)]
print(" || ".join(lines[-12:])[-3000:])
