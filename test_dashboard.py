from app import app, dashboard
with app.test_request_context('/dashboard'):
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'test'
        response = client.get('/dashboard')
        print(response.status_code)
