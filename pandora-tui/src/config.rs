use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct TuiConfig {
    pub daemon_url: String,
}

impl Default for TuiConfig {
    fn default() -> Self {
        Self {
            daemon_url: "http://127.0.0.1:7860".to_string(),
        }
    }
}

pub fn load_config() -> TuiConfig {
    let config_path = dirs_home().join(".config").join("pandora").join("config.toml");
    if !config_path.exists() {
        return TuiConfig::default();
    }

    let content = match std::fs::read_to_string(&config_path) {
        Ok(c) => c,
        Err(_) => return TuiConfig::default(),
    };

    let table: toml::Table = match content.parse() {
        Ok(t) => t,
        Err(_) => return TuiConfig::default(),
    };

    let host = table
        .get("server")
        .and_then(|s| s.get("host"))
        .and_then(|v| v.as_str())
        .unwrap_or("127.0.0.1");

    let port = table
        .get("server")
        .and_then(|s| s.get("port"))
        .and_then(|v| v.as_integer())
        .unwrap_or(7860);

    TuiConfig {
        daemon_url: format!("http://{}:{}", host, port),
    }
}

fn dirs_home() -> PathBuf {
    std::env::var("HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = TuiConfig::default();
        assert_eq!(config.daemon_url, "http://127.0.0.1:7860");
    }
}
