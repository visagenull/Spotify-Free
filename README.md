# Spotify Free

This Home Assistant integration provides an alternative way to control Spotify without requiring a premium account, offering extensive functionality through an unofficial Spotify API. It was developed with the help of ChatGPT and could be subject to changes or potential breakage as it relies on unofficial methods.

# Version 1.7 will break all compatibility with the built in Spotify integration.
To stop this ename the folder `spotify` containing the integration files to `spotify_free`, change the domain in `const.py` and the `manifest.json` to `spotify_free`. This will be compatible with the official spotify integration.

## Features

- **Playback Controls**: Play, Pause, Seek, and Skip tracks.
- **Playback Settings**: Adjust Shuffle and Repeat modes.
- **Volume Control**: Set and adjust the volume.
- **Device Management**: Select and switch playback devices.
- **Multi-Account Support**: Manage multiple Spotify accounts.
- **User Interface**: Configurable through Home Assistant's UI.
- **Real-Time Updates**: Uses WebSocket for live updates on playback status.

## Installation

### Using HACS

1. **Install HACS**: If you haven't already, follow the [HACS installation guide](https://hacs.xyz/docs/installation/manual).
2. **Add Custom Repository**:
   - Go to HACS in Home Assistant.
   - Navigate to `Settings` > `Custom repositories`.
   - Add `https://github.com/visagenull/Spotify-Free` as a custom repository.
   - Set the category to `Integration`.
3. **Install Integration**:
   - Go to the `Integrations` tab in HACS.
   - Search for "Spotify Free" and install it.

### Manual Installation

1. **Download Files**:
   - Copy all files from `custom_components/spotify_free` to `custom_components/spotify_free` in your Home Assistant configuration directory.
2. **Restart Home Assistant**: Ensure the new component is recognized by restarting Home Assistant.

## Configuration

### Obtaining `sp_dc` Cookie

To configure the integration, you need to obtain a `sp_dc` cookie from your Spotify account:

1. **Open Spotify**: Log in to your Spotify account via a web browser.
2. **Inspect Page**:
   - Open Developer Tools (usually accessible via F12 or right-click and select "Inspect").
   - Navigate to the `Application` tab.
   - In the left sidebar, select `Cookies` under `Storage`.
   - Find and copy the value of the `sp_dc` cookie from the `https://open.spotify.com` domain.

For more detailed steps on obtaining `sp_dc`, refer to [this guide](https://github.com/fondberg/spotcast/tree/master?tab=readme-ov-file#obtaining-sp_dc-and-sp_key-cookies).

### Configuration via UI

1. **Access Configuration**:
   - In Home Assistant, navigate to `Configuration` > `Integrations`.
   - Click on `+ Add Integration` and search for "Spotify Free".
2. **Add Credentials**:
   - Enter the `sp_dc` cookie value when prompted.
   - Follow additional prompts to complete the setup.

### Disabling Polling

To improve performance, you can disable polling:

1. **Navigate to the Home Assistant UI**:
   - Go to `Configuration` > `Settings` > `Entities`.
   - Locate the Spotify entity.
2. **Adjust Settings**:
   - Disable polling by unchecking the option or modifying the settings as outlined [here](https://github.com/home-assistant/home-assistant.io/issues/26198#issuecomment-1425561473).


## Notes

- **Device Selector**: The device selector in the UI will only become available after you have interacted with the Spotify media player at least once. This ensures that the integration can properly detect and list your available devices.

- **Potential Issues**: As this integration relies on unofficial APIs, it may encounter issues if Spotify updates its API or changes its cookie mechanisms. Regular updates and maintenance may be required to ensure continued functionality.

- **Community Support**: For questions or issues, refer to the [GitHub repository](https://github.com/visagenull/Spotify-Free) or engage with the Home Assistant community for support.
