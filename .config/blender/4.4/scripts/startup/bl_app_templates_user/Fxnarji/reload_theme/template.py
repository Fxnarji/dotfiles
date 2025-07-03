import bpy

def reload_theme(dummy):
    current_theme = bpy.context.preferences.themes[0].name

    all_themes = bpy.context.preferences.themes

    for theme in all_themes:
        if theme.name != current_theme:
            bpy.context.preferences.themes.active = theme
            break

    for theme in all_themes:
        if theme.name == current_theme:
            bpy.context.preferences.themes.active = theme
            break

# Register handler to run after Blender is fully loaded
def register():
    bpy.app.handlers.load_post.append(reload_theme)

def unregister():
    bpy.app.handlers.load_post.remove(reload_theme)

if __name__ == "__main__":
    register()
