import urllib.request, json, base64

req = json.loads(urllib.request.urlopen("http://localhost:4040/api/requests/http").read())
r = req["requests"][0]
print(f"Request Endpoint: {r['request']['uri']}")
req_body = base64.b64decode(r['request']['raw']).decode('utf-8', errors='ignore')
print(f"Request Body: {req_body}")
print(f"Status Code: {r['response']['status_code']}")
res_body = base64.b64decode(r['response']['raw']).decode('utf-8', errors='ignore')
print(f"Response Body: {res_body}")
