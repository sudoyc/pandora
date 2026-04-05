use crate::models::DownloadTask;

#[derive(Debug, Default)]
pub struct DownloadState {
    pub tasks: Vec<DownloadTask>,
    pub show_overlay: bool,
    pub active_count: u32,
}

impl DownloadState {
    pub fn update_from_ws(
        &mut self,
        gid: &str,
        event: &str,
        page: Option<u32>,
        total: Option<u32>,
        path: Option<&str>,
        error: Option<&str>,
    ) {
        match event {
            "download_progress" => {
                if let Some(task) = self.tasks.iter_mut().find(|t| t.gid == gid) {
                    task.status = "downloading".to_string();
                    if let (Some(p), Some(t)) = (page, total) {
                        task.downloaded_pages = p;
                        task.total_pages = t;
                    }
                }
            }
            "download_complete" => {
                if let Some(task) = self.tasks.iter_mut().find(|t| t.gid == gid) {
                    task.status = "complete".to_string();
                    if let Some(p) = path {
                        task.output_dir = p.to_string();
                    }
                }
            }
            "download_error" => {
                if let Some(task) = self.tasks.iter_mut().find(|t| t.gid == gid) {
                    task.status = "error".to_string();
                    if let Some(e) = error {
                        task.error = e.to_string();
                    }
                }
            }
            "download_cancelled" => {
                self.tasks.retain(|t| t.gid != gid);
            }
            _ => {}
        }
        self.active_count = self
            .tasks
            .iter()
            .filter(|t| t.status == "downloading" || t.status == "queued")
            .count() as u32;
        self.cleanup_completed();
    }

    /// Remove old completed/failed tasks, keeping at most 50.
    pub fn cleanup_completed(&mut self) {
        let terminal_count = self.tasks.iter()
            .filter(|t| t.status == "complete" || t.status == "error")
            .count();
        if terminal_count > 50 {
            let mut removed = 0;
            let to_remove = terminal_count - 50;
            self.tasks.retain(|t| {
                if removed >= to_remove {
                    return true;
                }
                if t.status == "complete" || t.status == "error" {
                    removed += 1;
                    return false;
                }
                true
            });
        }
    }
}
