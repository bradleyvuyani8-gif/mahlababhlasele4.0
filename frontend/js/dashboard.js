socket.onmessage = function(event){

    const data = JSON.parse(event.data);

    document.getElementById("symbol").innerText =
        `Pair: ${data.symbol}`;

    document.getElementById("price").innerText =
        `Price: ${data.last}`;

    document.getElementById("volume").innerText =
        `Volume: ${data.volume}`;
};
