from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.clients = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []

        for client in self.clients:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)

        for client in disconnected:
            self.disconnect(client)


manager = ConnectionManager()
