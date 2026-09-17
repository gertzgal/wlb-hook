on run argv
	set factText to item 1 of argv
	set timeoutSecs to (item 2 of argv) as integer
	tell me to activate
	set r to display dialog factText with title "Work-life balance" buttons {"Stop", "One last prompt", "Workaholic"} default button "Stop" cancel button "Stop" giving up after timeoutSecs
	if gave up of r then return "TIMEOUT"
	set choice to button returned of r
	if choice is not "Workaholic" then return choice
	set excuse to ""
	repeat while excuse is ""
		set r2 to display dialog "Workaholic mode unlocks the rest of the day. State your excuse (required):" default answer "" with title "Workaholic" buttons {"Submit"} default button "Submit" giving up after timeoutSecs
		if gave up of r2 then return "TIMEOUT"
		set excuse to text returned of r2
	end repeat
	return "Workaholic" & tab & excuse
end run
