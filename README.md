# VRChat Avatar Manager

A modern desktop application for browsing and downloading your VRChat unencrypted avatar bundles from VRC Servers

## Features

- **Browse VRChat Avatars**: View available avatars with filtering options
- **Search Functionality**: Find avatars by name, author, or description
- **Avatar Downloads**: Download avatar files (`.vrca`) to your local machine
- **User Authentication**: Secure login with 2FA support
- **Direct File Downloads**: Download any of your VRChat avatar files with the file downloader tool
- **Dark/Light Mode**: Switch between themes for comfortable viewing

## Installation

### Prerequisites

- Python 3.8 or higher
- PyQt6
- VRChat account

### Option 1: Run from Source

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/vrchat-avatar-manager.git
   cd vrchat-avatar-manager
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Run the application:
   ```
   python smp.py
   ```

### Option 2: Binary Release

1. Download the latest release from the [Releases page](https://github.com/yourusername/vrchat-avatar-manager/releases)
2. Extract the ZIP file
3. Run `SMP.exe`

## Setup and Configuration

1. **First Run**: 
   - On first launch, you'll need to log in with your VRChat credentials
   - The application will create a configuration directory for storing settings

2. **Authentication**:
   - Standard username/password login
   - Supports 2FA authentication (both authenticator app and email methods)

3. **Configuration**:
   - Settings are stored in `data/config.json`
   - Downloaded avatar thumbnails are cached in `data/images/`

## Usage Guide

### Avatar Browser

1. **Browse Avatars**: 
   - Select a filtering option from the dropdown
   - Use the search box to find specific avatars

2. **Avatar Details**:
   - Each card shows the avatar's name, author, and description

3. **Downloading an Avatar**:
   - Click the "Download" button on any avatar card
   - Choose where to save the .vrca file
   - The application will automatically download the avatar file

### File Downloader

1. **Direct Downloads**:
   - Enter a VRChat file URL (from Unity package, avatar, etc.)
   - Specify a save location
   - Click "Download File"

### Settings

- **Theme Toggle**: Switch between dark and light mode using the toggle in the top-right
- **Per-page Settings**: Change the number of avatars shown per page

## Privacy & Security

- Your VRChat credentials can be stored locally
- All API communication is done directly with VRChat's servers
- The application does not collect or send any data to third parties

## Troubleshooting

- **Login Issues**: 
  - Ensure your VRChat credentials are correct
  - If using 2FA, check that your authenticator app is synced correctly
  - Rate limited
   

- **Download Problems**:
  - Verify you have permission to access the avatar (It is uploaded to your account)
  - Check your internet connection
  - Review the logs tab for detailed error messages

## License

See the LICENSE file for details.

## Acknowledgments

- VRChat API community for documentation
- PyQt6 for the UI framework

