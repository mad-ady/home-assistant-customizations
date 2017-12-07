window.onload = function(){
	console.log("Js onLoad");
	clearIconAbsolute();
	h2IconSize();
}

function clearIconAbsolute(){
	var sheet = document.styleSheets[0];
	var rules = sheet.cssRules || sheet.rules;
	console.log("Extracted CSS rules");
	for(var i=0; i < rules.length; i++){
		//console.log("Looking at "+rules[i].selectorText);
		//do a regex to see if it's 
		// .widget-javascript-default-.* .icon
		if(/\.widget-(javascript|baseswitch)-default-.* \.icon/.test(rules[i].selectorText)){
			console.log("Found "+rules[i].selectorText);
			rules[i].style['position'] = "";
		}
	} 
}

function h2IconSize(){
	var sheet = document.styleSheets[0];
        var rules = sheet.cssRules || sheet.rules;
        console.log("Extracted CSS rules");
        for(var i=0; i < rules.length; i++){
		if(/h2/.test(rules[i].selectorText)){
			console.log("Found "+rules[i].selectorText);
			rules[i].style['font-size'] = '250%';
		}
	}
}
