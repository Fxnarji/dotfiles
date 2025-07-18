#

## 0.17
> 2024-11-22

* LSelect tool
	- support loop selection step limit

* Unfuck
	- support multiple independent selections
	- prevent propagation when working with edge-only geometry
		- and for multiple selections

* Fuse, Refude, QuadCorner tools
	- keep material indices (if multiple are used on a mesh)

* LoopTools wrappers
	- add Space wrapper
	- Circle wrapper
		- fix hang when using multiple independent selections
		- remove *fix midpoint* option for now

* Boolean tool
	- fix `TWO` key not working for scrolling down

* add update available indication in 3D view's sidebar and in addon prefs


## 0.16
> 2024-07-10

* CreateStash tool
	- apply mods on stashes, depending on mode your are in
		- stashing from object mode: apply modifiers on stash(es)
			- keep them by holding ALT key
		- stashing from edit mode: keep modifiers on stash
			- apply them by holding ALT key
		- unless you stash a specific face selection only
		- the tools tooltip reflects these changes, so reference that if you are ever unsure
	- re-enable fading wire drawing, accidentally left disabled previously

* BooleanApply tool
	- properly support redoing now
		- support individually toggling whether mods should be applied on original and operand object stashes
			- by default mods are not applied on the original object's stash
			- and are applied on the operand objects' stashes

* Symmetrize tool
	- when not mirroring vertex groups, remove the association on the affected verts, instead of just setting the weight to 0

* AddBoolean tool
	- fix import when setting up AutoSmooth in 4.1+

* Plug tool
	- fix exception when applying normal transfer as part of the plugging

* addon preferences
	- in Blender 4.2, when activating LoopTools wrappers in addon prefs support installing LoopTools from Blender extensions repo
	- on first addon registration, try to setup the MACHIN3tools `matcap_shiny_red.exr` for the NormalTransfer tool, if it can be found


## 0.15.3
> 2024-05-16

* Fuse tool
	- fix exception in BRIDGE mode, introduced accidentally in 0.15.2

* Boolean tool
	- simplify and speed up AutoSmooth setup, when toggling smoothing using `S` key

* Symmetrize tool
	- when not mirroring custom normals, expose option to mirror vgroups but default to False
	- fix exception when mirroring custom normals, when using transfer method to fix the center seam
	- improve HyperCursor integration

* Wedge tool
	- improve HyperCursor integration

* CreateStash tool
	- fix issues when trying to stash non-mesh objects

* preferences
	- add notes for `ALT + LEFTMOUSE` keymap, used by default for the Select wrapper, and should be remapped for people using `ALT` for navigation


## 0.15.2
> 2024-04-10

* Select tool/wrapper
	- fix issue in always_loop_select mode where you can't select additional edges

* Boolean tool
	- in Blender 4.1
		- when adding Auto Smooth mod, while existing Auto Smooth node trees are in the file, use the API<sup>which is faster!</sup>, rather than the blender op to add the mod

* NormalTransfer tool
	- prevent exception when having a selection of only sharp edges (no faces)
		- this is rather pointless, as you really want to select faces next to sharp edges, but now it longer errors out

* OffsetCut tool
	- fix rare exception when custom data layesr are still present from a previous run

* remove Blender-auto-added Auto Smooth mods, when bringing Plugs into the scene

* Fuse, Refuse, Unfuse, Unchamfer, Unbevel tools
	- support creating HyperCursor geometry gizmos

* Fuse, Refuse tools
	- support maintaining vertex groups on sweep verts

* addon preferences
	- update integrated updater to expose the Re-Scan button even if no update is found yet


## 0.15.1
> 2024-03-18


* Boolean tool
	- in Blender 4.1
		- when checking for existing Auto Smooth mods in the stack, that deviate from standard naming, support finding ones with index suffix in the node tree name


## 0.15
> 2024-03-17

* auto smooth and custom normal related fixes in Blender 4.1
	- Symmetrize tool
	- Nornmal Flatten and Straighten tools
	- Normal Transfer tool
	- Normal Clear tool
	- RealMirror tool
	- Plug tool
	- Boolean tool

* Boolean tool
	- support modifier based Auto Smooth in 4.1
		- when toggling (auto) smooth usnig `S` key, insert the mod towards the end of the stack, but always before Mirror and Array mods
	- init operator's auto smooth state and angle, from active object
	- when finishing with `LMB` unselect the active
	- hide cutters from rendering via cyclces visibility settings too now
	- when cancelling restore everything accordingly to its initial state
	- flesh out statusbar

* Symmetrize tool
	- expose redundant center edge removal threshold angle
	- increase it slighly from 0 to 0.05 to be more tolerant

* Select tool/wrapper
	- add *Always Loop Select* toggle
		- by default connected Sharps are selected, if entire edge selection consists of sharp edges, otherwise an angle based loop selection is done
		- with Always Loop Select enabled now, this behavior is overidden, so you don't constantly have to toggle back to loop selecting, when working on sharp edges


* CreatePlug, AddPlugToLibrary tools
	- ensure plug objects are properly render-able for the thumbnail

* Unchamfer tool
	- fix typo, causing exception in debug mode

* Stashes
	- improve how stashes HUD is drawn at the top of the 3D view
		- properly offset HUD downs depending on region_overlap pref, theme header alpha, and  header and tool header positioning
		- furthermore offset stashes HUD down, if MACHIN3tools focus tool active, and has its own HUD drawn
			
	- ViewStashes tool
		- improve edit stash object HUD in the same way
		- handle area and space data reference loss due to area maximizing or workspace space changes more gracefully
			- still not recommended to do, while in edit stash mode though

* handlers
	- rework when and how handler logic is executed
	- add asset drop cleanup handler (previously in MACHIN3tools) to automatically unlinke stash objects after dropping and asset using stashes from the asset browser

* GetSupport tool
	- improve the readme.html file, generated by the tool, providing more details on how to get to the system console
	- in Bender 4.1 (and 3.5) open the readme.html in the Browser automatically

* addon preferences
	- place Get Support button at top of addon prefs
	- add custom updater 
		- NOTE: since it's only introduced now in 0.15, it will only be of use for upcoming releases, so can't be used to install this very 0.15 update yet
		- allows for very easy addon update installation from .zip file, and from inside of Blender, instead of manually from the file browser
		- finds matching .zip file(s) in home and Downloads folder
		- allows selecting one of them them or manually selecting a file in any other location
		- extracts the file to a temporary location, and installs update when quitting Blender
		- like a manual update installation from the filebrowser, this maintains previous addon settings and custom keys
		- see installation instructions for details  
		- supports - and defaults to - keeping the current assets to prevent accidental loss
			
* fix issue with thankyou note after manual installation without removing previous installation
* fix plug library unloading messages sell being shown despite registration_debug pref being disabled

-----------------------------------------------------------------------------------------------------
