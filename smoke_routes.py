from app import create_app
import traceback

app = create_app()
app.testing = True
client = app.test_client()

urls = [
    '/sales',
    '/add_sale/invoice',
    '/invoice/1',
    '/receipt/1',
]

for url in urls:
    try:
        resp = client.get(url)
        print(url, resp.status_code)
        print(resp.get_data(as_text=True)[:600])
    except Exception:
        print(url, 'EXC')
        traceback.print_exc()
