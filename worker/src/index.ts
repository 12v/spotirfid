interface Env {
  SPOTIFY_CLIENT_ID: string;
  SPOTIFY_CLIENT_SECRET: string;
  READER_CONFIG: KVNamespace;
  TAG_MAP: KVNamespace;
  TOKEN_CACHE: KVNamespace;
}

interface ReaderConfig {
  refreshToken: string;
  targetDevice: string;
  name?: string;
}

interface ScanRequest {
  readerId: string;
  tagId: string;
  isWriteMode: boolean;
}

interface ScanResponse {
  success: boolean;
  action: 'play' | 'mapped' | 'error';
  message: string;
}

interface SpotifyDevice {
  id: string;
  name: string;
  type: string;
  is_active: boolean;
}

interface SpotifyCurrentlyPlaying {
  item?: {
    album?: {
      uri: string;
      name: string;
    };
  };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    const url = new URL(request.url);
    if (url.pathname !== '/api/scan') {
      return new Response('Not found', { status: 404 });
    }

    try {
      const body: ScanRequest = await request.json();
      const result = await handleScan(body, env);
      return Response.json(result);
    } catch (error) {
      console.error('Error handling scan:', error);
      return Response.json({
        success: false,
        action: 'error',
        message: error instanceof Error ? error.message : 'Unknown error'
      } as ScanResponse, { status: 500 });
    }
  }
};

async function handleScan(req: ScanRequest, env: Env): Promise<ScanResponse> {
  const { readerId, tagId, isWriteMode } = req;

  const readerConfig = await getReaderConfig(readerId, env);
  if (!readerConfig) {
    return {
      success: false,
      action: 'error',
      message: 'Invalid reader ID'
    };
  }

  if (isWriteMode) {
    return await handleWriteMode(readerId, tagId, readerConfig, env);
  } else {
    return await handlePlayMode(readerId, tagId, readerConfig, env);
  }
}

async function getReaderConfig(readerId: string, env: Env): Promise<ReaderConfig | null> {
  const configJson = await env.READER_CONFIG.get(readerId);
  if (!configJson) {
    return null;
  }
  try {
    return JSON.parse(configJson) as ReaderConfig;
  } catch {
    return null;
  }
}

async function handlePlayMode(readerId: string, tagId: string, readerConfig: ReaderConfig, env: Env): Promise<ScanResponse> {
  const kvKey = `${readerId}:${tagId}`;
  const spotifyUri = await env.TAG_MAP.get(kvKey);

  if (!spotifyUri) {
    return {
      success: false,
      action: 'error',
      message: `Tag ${tagId} not mapped to any Spotify URI`
    };
  }

  const accessToken = await getAccessToken(readerId, readerConfig, env);
  const deviceId = await findDeviceId(accessToken, readerConfig.targetDevice);

  if (!deviceId) {
    return {
      success: false,
      action: 'error',
      message: `Device "${readerConfig.targetDevice}" not found`
    };
  }

  await startPlayback(accessToken, deviceId, spotifyUri);

  return {
    success: true,
    action: 'play',
    message: `Playing ${spotifyUri}`
  };
}

async function handleWriteMode(readerId: string, tagId: string, readerConfig: ReaderConfig, env: Env): Promise<ScanResponse> {
  const accessToken = await getAccessToken(readerId, readerConfig, env);
  const currentlyPlaying = await getCurrentlyPlaying(accessToken);

  if (!currentlyPlaying?.item?.album?.uri) {
    return {
      success: false,
      action: 'error',
      message: 'No album currently playing'
    };
  }

  const albumUri = currentlyPlaying.item.album.uri;
  const albumName = currentlyPlaying.item.album.name;

  const kvKey = `${readerId}:${tagId}`;
  await env.TAG_MAP.put(kvKey, albumUri);

  return {
    success: true,
    action: 'mapped',
    message: `Mapped tag ${tagId} to album: ${albumName}`
  };
}

async function getAccessToken(readerId: string, readerConfig: ReaderConfig, env: Env): Promise<string> {
  const cacheKey = `${readerId}:access_token`;
  const cached = await env.TOKEN_CACHE.get(cacheKey);
  if (cached) {
    return cached;
  }

  const response = await fetch('https://accounts.spotify.com/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'Authorization': 'Basic ' + btoa(`${env.SPOTIFY_CLIENT_ID}:${env.SPOTIFY_CLIENT_SECRET}`)
    },
    body: new URLSearchParams({
      grant_type: 'refresh_token',
      refresh_token: readerConfig.refreshToken
    })
  });

  if (!response.ok) {
    throw new Error(`Token refresh failed: ${response.statusText}`);
  }

  const data: any = await response.json();
  const accessToken = data.access_token;
  const expiresIn = data.expires_in || 3600;

  await env.TOKEN_CACHE.put(cacheKey, accessToken, {
    expirationTtl: expiresIn - 60
  });

  return accessToken;
}

async function findDeviceId(accessToken: string, deviceName: string): Promise<string | null> {
  const response = await fetch('https://api.spotify.com/v1/me/player/devices', {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });

  if (!response.ok) {
    throw new Error(`Get devices failed: ${response.statusText}`);
  }

  const data: { devices: SpotifyDevice[] } = await response.json();
  const device = data.devices.find(d => d.name === deviceName);

  return device?.id || null;
}

async function startPlayback(accessToken: string, deviceId: string, uri: string): Promise<void> {
  const body: any = {
    device_id: deviceId
  };

  if (uri.includes(':album:') || uri.includes(':playlist:')) {
    body.context_uri = uri;
  } else {
    body.uris = [uri];
  }

  const response = await fetch('https://api.spotify.com/v1/me/player/play', {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${accessToken}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });

  if (!response.ok && response.status !== 204) {
    const error = await response.text();
    throw new Error(`Start playback failed: ${error}`);
  }
}

async function getCurrentlyPlaying(accessToken: string): Promise<SpotifyCurrentlyPlaying> {
  const response = await fetch('https://api.spotify.com/v1/me/player/currently-playing', {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  });

  if (response.status === 204) {
    return {};
  }

  if (!response.ok) {
    throw new Error(`Get currently playing failed: ${response.statusText}`);
  }

  return await response.json();
}
