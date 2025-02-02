const $ipInput = document.querySelector('#ip-input');
const $nameInput = document.querySelector('#name-input');
const $button = document.querySelector('#connect-button');

// process user input and save to storage
$ipInput.addEventListener('input', (e) => {
	const { value } = e.currentTarget;
	chrome.storage.sync.set({ cacheSongGuesserIP: value });
});

// get the IP data in storage
async function fetchData() {
	chrome.storage.sync.get(null, (storage) => {
		if (storage.cacheSongGuesserIP === undefined)
			$ipInput.value = "127.0.0.1:5555";
		else
			$ipInput.value = storage.cacheSongGuesserIP;
		
		if (storage.cacheSongGuesserName === undefined)
			$nameInput.value = "Anonymous";
		else
			$nameInput.value = storage.cacheSongGuesserName;
	});
}
window.onload = () => {
	document.title = "Song Guesser Extension";
	fetchData();
}

var verifyCount = 0;
// connect button event
document.addEventListener('DOMContentLoaded', function() {
    $button.addEventListener('click', function() {
		chrome.storage.sync.set({ cacheSongGuesserIP: $ipInput.value });  // always save content before connect
		chrome.storage.sync.set({ cacheSongGuesserName: $nameInput.value });  // always save content before connect
		// test websocket connection
		let ws = new WebSocket("wss://" + $ipInput.value);
		ws.onerror = () => {
			alert("Please accept connection on the next page and try again");
			
			verifyCount = 0;
			chrome.tabs.create({ url: "https://" + $ipInput.value }, function(tab) {
				function tabUpdateListener(tabId, changeInfo, updatedTab) {
					if (tabId === tab.id && changeInfo.status === "complete") {
						if (++verifyCount > 1) {
							chrome.tabs.remove(tabId);
							alert("Connection accepted!");
							$button.click();
						}
					}
				}
				function tabRemoveListener(tabId, removeInfo) {
					if (tabId === tab.id) {
						chrome.tabs.onUpdated.removeListener(tabUpdateListener);
						chrome.tabs.onRemoved.removeListener(tabRemoveListener);
					}
				}
				
				chrome.tabs.onUpdated.addListener(tabUpdateListener);
				chrome.tabs.onRemoved.addListener(tabRemoveListener);
			});
		}
		ws.onopen = () => {
			ws.close();
			
			// window.location.href = "./main.html";
			chrome.tabs.update({url:`https://www.youtube.com/watch?v=6zg0JvlpYZ4&songGuesserIP=${$ipInput.value}&nickname=${$nameInput.value}`});
		}
    });
});
