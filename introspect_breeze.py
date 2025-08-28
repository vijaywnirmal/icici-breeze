from breeze_connect import BreezeConnect

client = BreezeConnect(api_key="dummy")
methods = [m for m in dir(client) if not m.startswith("_")]
print("METHODS:")
for name in methods:
	print(name)
