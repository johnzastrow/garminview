# Where should we write the GIF?
Output demo.gif

Set FontSize 14
Set Width 900
Set Height 600
Set LetterSpacing 0
Set LineHeight 1
Set TypingSpeed 1ms # 500ms
# the typing speed of seconds per key press. For example, a typing speed of 0.1 would result in a 0.1s (100ms) delay between each character being typed.
# Padding (in pixels) of the terminal frame with the Set Padding command.
Set Padding 0
# Set Theme { "name": "Whimsy", "black": "#535178", "red": "#ef6487", "green": "#5eca89", "yellow": "#fdd877", "blue": "#65aef7", "magenta": "#aa7ff0", "cyan": "#43c1be", "white": "#ffffff", "brightBlack": "#535178", "brightRed": "#ef6487", "brightGreen": "#5eca89", "brightYellow": "#fdd877", "brightBlue": "#65aef7", "brightMagenta": "#aa7ff0", "brightCyan": "#43c1be", "brightWhite": "#ffffff", "background": "#29283b", "foreground": "#b3b0d6", "selection": "#3d3c58", "cursor": "#b3b0d6" }
# the type of window bar (Colorful, ColorfulRight, Rings, RingsRight) on the terminal window with the Set WindowBar command.
Set WindowBar Colorful
# the playback speed of the final render.
Set PlaybackSpeed 1 # Make output 1 times slower
# Themes at https://github.com/charmbracelet/vhs/blob/main/THEMES.md
# Set Theme "Retrowave"
Set FontFamily "FiraCode Nerd Font Mono Med"


Type "echo 'Starting with the basics'"
Enter
Sleep 2.5s

# The offset for when the GIF loop should begin. This allows you to make the first frame of the GIF (generally used for previews) more interesting.

# Set LoopOffset 5 # Start the GIF at the 5th frame
# Set LoopOffset 50% # Start the GIF halfway through


Type "echo 'if Playback was 0.5 - it would Make output 2 times slower' "
Enter
Sleep 2.5s
# the theme of the terminal with the Set Theme command. The theme value should be a JSON string with the base 16 colors and foreground + background.

Type "echo 'Theme will be manual' "
Enter
Sleep 2.5s

Type "echo 'Padding is zero' "
Enter
Sleep 2.5s
Enter
# Escape single and double quotes with backticks.
Type `VAR="Escaped"`
Enter
Enter


# Type a command in the terminal.
Type "echo 'Welcome to VHS!'"
Enter
Enter

Type "echo 'taking a screenshot' "
Enter
Sleep 2.5s
# At any point...
Screenshot Normal.png

# Pause for dramatic effect...
Sleep 500ms

Type "echo 'setting theme to retrowave "
Enter
Sleep 2.5s
Enter
# Type "echo 'trying btop to check screen size' "
Enter
# Type "btop"
# Enter
# Sleep 13s
Enter
Type "q"
Enter
Type "echo 'btop doesn't work' "



# The Screenshot command captures the current frame (png format).

Type "echo 'another screenshot "
Enter
Sleep 2.5s

# At any point...
Screenshot Retro.png



Type "echo 'setting windowbar "
Enter
Sleep 2.5s



# Run the command by pressing enter.
Enter

# Admire the output for a bit.
Sleep 5s
