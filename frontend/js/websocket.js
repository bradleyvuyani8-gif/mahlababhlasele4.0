const socket = new WebSocket(
    `ws://${window.location.host}/ws`
);

socket.onopen = () => {
    console.log("WebSocket Connected");
};

socket.onclose = () => {
    console.log("WebSocket Disconnected");
};

socket.onerror = (error) => {
    console.error(error);
};
