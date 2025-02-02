const sanitizePolicy = trustedTypes.createPolicy('sanitizePolicy', { createHTML: (string) => string });

const YTPlayerState = {
	UNLOADED: -1,
	ENDED: 0,
	PLAYING: 1,
	PAUSED: 2,
	BUFFERING: 3,
	CUED: 5
}

// ============= WebSocket server protocol ============= //

// send msg to WebSocket server
function sendMsg(msg) {
	if (ws === undefined)
		return;
	
	var data = JSON.stringify(msg);
	ws.send(data);
}
// on WebSocket connected
function onConnected() {
	$ipInfo.innerHTML = sanitizePolicy.createHTML("Connected to " + songGuesserIP);
	sendMsg({"type": "name", "name": nickName});
};
// on WebSocket connect failed
// function onConnectFailed() {
	// $ipInfo.innerHTML = sanitizePolicy.createHTML("Can not connect to " + songGuesserIP);
// };
// on WebSocket server closed
function onServerClosed() {
	if (selfClosing)
		return;
	
	alert("Remote server closed!");
	history.back();
};

function rebuildPlayerlist(needSort) {
	if (needSort) {
		userList.sort(function(a, b) {
			if (a.score != b.score)
				return b.score - a.score;
			return a.id - b.id;
		});
	}
	
	for (let i = 0; i < userList.length; i++) {
		const userID = userList[i].id;
		const userName = userList[i].name;
		const userScore = userList[i].score;
		const userGuess = userList[i].guessed;
		
		if (i >= playerlistObjs.length) {
			let itemFrame = document.createElement("div");
			itemFrame.className = "playerlist-item";
			
				// TODO: show player avatar
				// let img = document.createElement("img");
				// let imageUrl = "https://i.ytimg.com/vi/" + videoID + "/default.jpg";
				// img.src = imageUrl
				// itemFrame.appendChild(img);
				
				let infoFrame = document.createElement("div");
				infoFrame.className = "playerlist-item-info";
				itemFrame.appendChild(infoFrame);
				
					let name = document.createElement("p");
					name.className = "playerlist-item-info-text";
					name.style.height = "60%";
					infoFrame.appendChild(name);
					
					let score = document.createElement("p");
					score.className = "playerlist-item-info-text";
					score.style.height = "20%";
					score.style["text-wrap"] = "nowrap";
					infoFrame.appendChild(score);
				
				let guessOverlay = document.createElement("div");
				guessOverlay.className = "guess-overlay";
				itemFrame.appendChild(guessOverlay);
			
			$playerlistContainer.appendChild(itemFrame);
			playerlistObjs.push({ obj: itemFrame, nameObj: name, scoreObj: score, overlayObj: guessOverlay });
		}
		
		// write user name and current state
		if (userID == selfUserID)
			playerlistObjs[i].obj.style["background-color"] = "#fff";
		else
			playerlistObjs[i].obj.style["background-color"] = "#999";
			
		playerlistObjs[i].nameObj.innerHTML = sanitizePolicy.createHTML(`[${userID}] ${userName}`);
		playerlistObjs[i].scoreObj.innerHTML = sanitizePolicy.createHTML(`SCORE: ${userScore}`);
		if (userGuess != null) {
			playerlistObjs[i].overlayObj.style.visibility = "visible";
			if (userID == scoredPlayerID)
				playerlistObjs[i].overlayObj.style.color = "yellow";
			else
				playerlistObjs[i].overlayObj.style.color = "gray";
			
			if (userGuess == "")
				playerlistObjs[i].overlayObj.innerHTML = sanitizePolicy.createHTML("SKIP");
			else
				playerlistObjs[i].overlayObj.innerHTML = sanitizePolicy.createHTML(userGuess);
		}
		else {
			playerlistObjs[i].overlayObj.style.visibility = "hidden";
		}
	}
	
	// remove redundant elements
	for (let i = userList.length; i < playerlistObjs.length; i++)
		$playerlistContainer.removeChild(playerlistObjs[i]);
}
// on receive WebSocket server msg
function onReceive(e) {
	var msg = JSON.parse(e.data);
	switch (msg.type) {
		case "load":
			if (!ytPlayerReady)
				break;
			
			playingID = msg.vid;
			ytPlayer.cueVideoById(playingID);
			break;
			
		case "play":
			if (!ytPlayerReady)
				break;
			if (playingID == undefined)
				break;
			
			ytPlayer.seekTo(msg.start, true);
			ytPlayer.playVideo();
			let interv = function() {
				if (!document.querySelector("div.ad-showing") && ytPlayer.getCurrentTime() >= msg.end) {
					ytPlayer.pauseVideo();
					return;
				}
				setTimeout(interv, 20);
			}
			break;
			
		case "uid":
			selfUserID = msg.id;
			displayUserID.innerHTML = sanitizePolicy.createHTML(selfUserID);
			break;
			
		case "userlist":
			if (userList.length < msg.list.length)
				window.postMessage({"type": "join_sound"});
			else if (userList.length > msg.list.length)
				window.postMessage({"type": "leave_sound"});
			
			userList = msg.list;
			rebuildPlayerlist(true);
			break;
			
		case "qset":
			questionSet = msg.data;
			targetQuestionCount = msg.count;
			// TODO: update question set display
			break;
			
		case "qcount":
			targetQuestionCount = msg.count;
			// TODO: update target question count display
			break;
			
		case "gstate":
			questionNumber = msg.qnum;
			questionPart = msg.part;
			scoredPlayerID = undefined;
			// TODO: update game state related display
			if (questionNumber < 0) {
				// game not started
			}
			else {
				// update question number and part
			}
			break;
			
		case "start":
			for (let i = 0; i < userList.length; i++)
				userList[i].score = 0;
			// TODO: rearrange userlist and update display
			// TODO: show start countdown (5 seconds)
			break;
			
		case "guess":
			for (let i = 0; i < userList.length; i++) {
				if (userList[i].id == msg.uid) {
					userList[i].guessed = msg.guess;
					// TODO: update player guessed answer display
					rebuildPlayerlist(false);
					break;
				}
			}
			break;
			
		case "score":
			scoredPlayerID = msg.uid;
			for (let i = 0; i < userList.length; i++) {
				if (userList[i].id == scoredPlayerID) {
					userList[i].score++;
					// TODO: rearrange userlist and update display
					rebuildPlayerlist(true);
					break;
				}
			}
			break;
			
		case "reveal":
			let validAnswers = msg.answers;
			// TODO: reveal youtube player and show valid answers
			break;
			
		case "result":
			// TODO: show final result and winner by playerList data
			break;
	}
};

// Youtube Player state changed
function onPlayerStateChanged(e) {
	if (playingID == undefined) {
		if (e == YTPlayerState.PLAYING)
			ytPlayer.cueVideoById("0");
		return;
	}
	
	switch (e) {
		case YTPlayerState.CUED:
			sendMsg({"type": "loaded", "id": playingID});
			break;
		// case YTPlayerState.PAUSED:
			// break;
		// case YTPlayerState.ENDED:
			// break;
		// case YTPlayerState.PLAYING:
			// break;
		// case YTPlayerState.UNLOADED:
			// break;
		// case YTPlayerState.BUFFERING:
			// break;
	}
}

// Youtube video can not play
function onVideoError(e) {
	if (playingID == undefined)
		return;
	
	sendMsg({"type": "loaded", "error": true});
}



function getParameterValue(parameterName) {
	var params = {};
    var query = window.location.search.substring(1);
    var vars = query.split('&');
    for (var i = 0; i < vars.length; i++) {
        var pair = vars[i].split('=');
		params[decodeURIComponent(pair[0])] = decodeURIComponent(pair[1]);
    }
	return params;
}
var urlParams = getParameterValue();
var songGuesserIP = urlParams["songGuesserIP"];
var nickName = urlParams["nickname"];
if (songGuesserIP != null) {
	var selfClosing = false;

	var initCheck;
	var ytPlayer;
	var htmlVideo;
	var ytPlayerReady = false;

	var searchResultPlaylist = [];
	var playlistPreviewItems = [];

	var ws = undefined;
	var playerlistObjs = [];  // client playlist objects
	var playingID = undefined;

	var userList = [];
	var selfUserID;
	var scoredPlayerID;

	var questionSet;
	var targetQuestionCount = -1;
	
	window.addEventListener("message", (event) => {
		let msg = event.data;
		switch (msg.type) {
			case "init_volume":
				soundSlider.value = msg.value;
				soundVolumeText.innerHTML = sanitizePolicy.createHTML(`${msg.value}%`);
				break;
		}
	});
	// Inject some HTML elements =======================================================
	
	var renameFrame = document.createElement("div");
	renameFrame.id = "rename-frame";
	
		var displayUserID = document.createElement("a");
		displayUserID.id = "rename-show-id";
		renameFrame.appendChild(displayUserID);
		
		let renameInput = document.createElement("textarea");
		renameInput.id = "rename-input";
		renameInput.value = nickName;
		renameFrame.appendChild(renameInput);
		
		let renameButton = document.createElement("button");
		renameButton.id = "rename-button";
		renameButton.innerHTML = sanitizePolicy.createHTML("rename");
		renameButton.addEventListener("click", function() {
			if (renameInput.value != nickName)
				sendMsg({"type": "name", "name": renameInput.value});
		});
		renameFrame.appendChild(renameButton);
	
	let settingButton = document.createElement("button");
	settingButton.id = "setting-button";
	settingButton.innerHTML = sanitizePolicy.createHTML("⚙︎");
	settingButton.addEventListener("click", function() {
		settingFrame.style.visibility = "visible";
	});
	
	var settingFrame = document.createElement("button");
	settingFrame.className = "mask-button";
	settingFrame.style.visibility = "hidden";
	settingFrame.addEventListener("click", function(e) {
		e.stopPropagation();
		settingFrame.style.visibility = "hidden";
	});
	
		let settingPanel = document.createElement("div");
		settingPanel.id = "setting-panel";
		settingPanel.onclick = function(e) { e.stopPropagation(); }
		settingFrame.appendChild(settingPanel);
		
			let soundSliderTitle = document.createElement("h3");
			soundSliderTitle.innerHTML = sanitizePolicy.createHTML("System Sound Volume");
			soundSliderTitle.style.color = "#fff";
			settingPanel.appendChild(soundSliderTitle);
			
			let soundSlider = document.createElement("input");
			soundSlider.type = "range";
			soundSlider.className = "slider";
			soundSlider.min = "0";
			soundSlider.max = "100";
			soundSlider.value = "40";
			soundSlider.oninput = function(e) {
				soundVolumeText.innerHTML = sanitizePolicy.createHTML(`${this.value}%`);
				window.postMessage({"type": "sound_volume", "value": this.value});
			}
			settingPanel.appendChild(soundSlider);
		
			var soundVolumeText = document.createElement("span");
			soundVolumeText.innerHTML = sanitizePolicy.createHTML("40%");
			soundVolumeText.style.color = "#fff";
			settingPanel.appendChild(soundVolumeText);
	
	var $ipInfo = document.createElement("label");
	$ipInfo.id = "connecting-ip";
	
	var $playerlistContainer = document.createElement("div");
	$playerlistContainer.id = "playerlist";
	
	var guessField = document.createElement("div");
	guessField.id = "guess-field";
	
		let guessInputLabel = document.createElement("h3");
		guessInputLabel.for = "guess-input";
		guessInputLabel.innerHTML = sanitizePolicy.createHTML("Guess:");
		guessField.appendChild(guessInputLabel);
		
		let guessInput = document.createElement("textarea");
		guessInput.id = "guess-input";
		guessInput.rows = "1";
		guessField.appendChild(guessInput);
		
		let skipGuessButton = document.createElement("button");
		skipGuessButton.id = "guess-skip-button";
		skipGuessButton.innerHTML = sanitizePolicy.createHTML("SKIP");
		skipGuessButton.addEventListener("click", function() {
			sendMsg({"type": "guess", "answer": ""});
			guessInput.value = "";
		});
		guessField.appendChild(skipGuessButton);
		
	// =================================================================================
	
	document.addEventListener("keydown", function(event) {
		if (document.activeElement.tagName.toLowerCase() == "textarea")
			return;
		
		event.preventDefault();
		event.stopPropagation();
	});
	window.addEventListener("load", () => {
		$ipInfo.innerHTML = sanitizePolicy.createHTML("Connecting to " + songGuesserIP);

		ws = new WebSocket("wss://" + songGuesserIP);
		ws.onopen = onConnected;
		ws.onerror = onServerClosed; //onConnectFailed;
		ws.onclose = onServerClosed;
		ws.onmessage = onReceive;
	});
	window.onbeforeunload = function() {
		if (ws !== undefined) {
			selfClosing = true;
			ws.close();
		}
	}
	
	initCheck = setInterval(() => {
		document.title = "Song Guesser";
		ytPlayer = document.getElementById("movie_player");
		if (ytPlayer != undefined && !ytPlayerReady) {
			ytPlayer.addEventListener("onStateChange", onPlayerStateChanged);
			ytPlayer.addEventListener("onError", onVideoError);
			ytPlayer.loadVideoById("0");
			ytPlayerReady = true;
		}
		htmlVideo = document.getElementsByTagName("video")[0];
		
		let topBar = document.getElementById("masthead-container");
		let rightFrame = document.getElementById("related");
		let belowFrame = document.getElementById("below");
		let nextButton = document.getElementsByClassName("ytp-next-button")[0];
		let miniPlayerButton = document.getElementsByClassName("ytp-miniplayer-button")[0];
		let sizeControlButton = document.getElementsByClassName("ytp-size-button")[0];
		if (!ytPlayer || !htmlVideo || !rightFrame || !topBar || !belowFrame || !nextButton || !miniPlayerButton || !sizeControlButton)
			return;
		
		document.body.appendChild(renameFrame);
		document.body.appendChild(settingButton);
		document.body.appendChild(settingFrame);
		
		topBar.innerHTML = sanitizePolicy.createHTML("");
		topBar.appendChild($ipInfo);
		
		let tmpElement = rightFrame;
		rightFrame = rightFrame.parentElement;
		rightFrame.removeChild(tmpElement);
		rightFrame.appendChild(playlistControlFrame);
		rightFrame.appendChild($playerlistContainer);
		
		belowFrame.style.visibility = "hidden";
		belowFrame.prepend(guessField);
		
		nextButton.parentElement.removeChild(nextButton);
		miniPlayerButton.parentElement.removeChild(miniPlayerButton);
		sizeControlButton.parentElement.removeChild(sizeControlButton);
		
		// stop the video before it ends to avoid autoplay
		htmlVideo.ontimeupdate = () => {
			if (ytPlayer.getPlayerState() == YTPlayerState.PLAYING && htmlVideo.duration - htmlVideo.currentTime < 0.5)
				ytPlayer.cancelPlayback();
		}
		
		clearInterval(initCheck);
	}, 100);
}