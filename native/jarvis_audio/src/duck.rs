//! The ducking rules, free of any Windows call so they can be tested: what to lower, to what level, and when to give it back.

/// Sessions quieter than this are left alone (nothing audible to lower).
pub const MIN_AUDIBLE: f32 = 0.02;
/// Volume other apps are lowered to while Jarvis speaks, if they were louder.
pub const DUCK_LEVEL: f32 = 0.45;

/// New volume for a session that is currently at `current`, or None when it should not be touched.
pub fn target_for(current: f32) -> Option<f32> {
    if current <= MIN_AUDIBLE {
        return None;
    }
    let target = current.min(DUCK_LEVEL);
    (target < current).then_some(target)
}

/// Nested duck requests: only the first one lowers and only the last release restores.
#[derive(Default, Debug)]
pub struct Counter {
    depth: u32,
}

#[derive(Debug, PartialEq, Eq)]
pub enum Step {
    Lower,
    Restore,
    Nothing,
}

impl Counter {
    pub fn enable(&mut self) -> Step {
        self.depth += 1;
        if self.depth == 1 {
            Step::Lower
        } else {
            Step::Nothing
        }
    }

    /// `has_saved` is whether anything was actually lowered; a release without it has nothing to give back.
    pub fn disable(&mut self, has_saved: bool) -> Step {
        self.depth = self.depth.saturating_sub(1);
        if self.depth == 0 && has_saved {
            Step::Restore
        } else {
            Step::Nothing
        }
    }

    pub fn reset(&mut self) {
        self.depth = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_louder_audible_sessions_are_lowered() {
        assert_eq!(target_for(1.0), Some(0.45));
        assert_eq!(target_for(0.46), Some(0.45));
        assert_eq!(target_for(0.45), None);
        assert_eq!(target_for(0.3), None);
        assert_eq!(target_for(0.02), None);
        assert_eq!(target_for(0.0), None);
    }

    #[test]
    fn nested_requests_lower_once_and_restore_once() {
        let mut c = Counter::default();
        assert_eq!(c.enable(), Step::Lower);
        assert_eq!(c.enable(), Step::Nothing);
        assert_eq!(c.disable(true), Step::Nothing);
        assert_eq!(c.disable(true), Step::Restore);
    }

    #[test]
    fn an_extra_release_does_not_underflow_and_force_reset_clears_the_depth() {
        let mut c = Counter::default();
        assert_eq!(c.disable(false), Step::Nothing);
        assert_eq!(c.enable(), Step::Lower);
        c.reset();
        assert_eq!(c.enable(), Step::Lower);
        assert_eq!(c.disable(false), Step::Nothing);
    }
}
