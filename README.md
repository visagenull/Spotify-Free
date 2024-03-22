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
<!---This component is easiest installed using [HACS](https://github.com/custom-components/hacs). -->

To install manually copy all the files from ```custom_components/spotify_free``` to ```custom_components/spotify_free``` in your Home Assistant folder.

## Configuration

The integration is configured with the UI.  
You will need  a spotify ```sp_dc``` key which can be found by inspecting a logged in Spotify page on your browser.  

This is found in Application > Storage > Cookies > ```https://open.spotify.com``` > ```sp_dc```

Follow [this](https://github.com/fondberg/spotcast/tree/master?tab=readme-ov-file#obtaining-sp_dc-and-sp_key-cookies) guide for a similar process.
