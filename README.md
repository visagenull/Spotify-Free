# Spotify Free

This Home Assistant integration is designed to provide full parity of the Spotify media player integration without requiring a premium account while also providing better functionality.  

**This uses an unnoficial Spotify API and was mostly written by ChatGPT so could break at any time.**

## Features

* Play/Pause/Seek/Skip
* Shuffle/Repeat
* Volume control
* Device select
* Multiple accounts
* UI configuration
* Websocket based updates

## Installation
This component is easiest installed using [HACS](https://github.com/custom-components/hacs).


To install manually copy all the files from ```custom_components/spotify_free``` to ```custom_components/spotify_free``` in your Home Assistant folder.  

[Add](https://hacs.xyz/docs/faq/custom_repositories/) ```https://github.com/lw-8991/Spotify-Free``` as a custom reposity with the integration category in HACS then configure via the UI.

## Configuration

The integration is configured with the UI.  
You will need  a spotify ```sp_dc``` key which can be found by inspecting a logged in Spotify page on your browser.  

This is found in Application > Storage > Cookies > ```https://open.spotify.com``` > ```sp_dc```

Follow [this](https://github.com/fondberg/spotcast/tree/master?tab=readme-ov-file#obtaining-sp_dc-and-sp_key-cookies) guide for a similar process.  

You can disable polling via the UI like [this](https://github.com/home-assistant/home-assistant.io/issues/26198#issuecomment-1425561473) as it is not needed.  

## Notes
The device seletor will not be available until you have interacted with the Spotify media player.
