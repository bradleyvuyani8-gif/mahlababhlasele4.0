socket.onmessage = (event) => {

    const data = JSON.parse(event.data);

    document.getElementById("symbol").textContent =
        `Pair: ${data.symbol}`;

    document.getElementById("price").textContent =
        `Price: ${data.last}`;

    document.getElementById("volume").textContent =
        `Volume: ${data.volume}`;
};
