//! The crate's parse error type.

/// M2 parse error.
#[derive(Debug)]
pub enum Error {
    NotMd20,
    UnsupportedVersion(u32),
    Truncated,
    /// A skin profile without its `SKIN` magic.
    NotSkin,
    /// A skin section whose start passes `u16` (3.3.5a's `level` is set), which 1.12.1 cannot hold.
    SkinSectionPastU16(usize),
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::NotMd20 => write!(f, "not an MD20 model"),
            Error::UnsupportedVersion(v) => {
                write!(
                    f,
                    "unsupported M2 version {v} (expected 256..=263, or 264 through relayout_264)"
                )
            }
            Error::Truncated => write!(f, "truncated M2"),
            Error::NotSkin => write!(f, "not a SKIN profile"),
            Error::SkinSectionPastU16(i) => {
                write!(
                    f,
                    "skin section {i} starts past 65535, which version 256 cannot hold"
                )
            }
        }
    }
}
impl std::error::Error for Error {}
pub(crate) type Result<T> = std::result::Result<T, Error>;
