var soundVolume;
var joinSound = new Audio(chrome.runtime.getURL("sounds/user_join.mp3"));
var leaveSound = new Audio(chrome.runtime.getURL("sounds/user_leave.mp3"));

function setSoundVolume(volume) {
	soundVolume = volume;
	joinSound.volume = soundVolume;
	leaveSound.volume = soundVolume;
	chrome.storage.sync.set({ watchTogetherSoundVolume: volume });
}



// get the setting data in storage
async function fetchData() {
	chrome.storage.sync.get(null, (storage) => {
		if (storage.watchTogetherSoundVolume === undefined)
			setSoundVolume(0.4);
		else
			setSoundVolume(storage.watchTogetherSoundVolume);
		
		window.postMessage({"type": "init_volume", "value": soundVolume * 100});
	});
}
window.addEventListener("load", () => {
	fetchData();
});

window.addEventListener("message", (event) => {
	let msg = event.data;
	switch (msg.type) {
		case "join_sound":
			joinSound.play();
			break;
		case "leave_sound":
			leaveSound.play();
			break;
		case "sound_volume":
			setSoundVolume(msg.value / 100);
			break;
		case "set_player_id":
			chrome.storage.sync.set({ cacheSongGuesserID: msg.id });
			break;
	}
});