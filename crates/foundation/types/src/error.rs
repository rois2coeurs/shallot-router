use thiserror::Error;

#[derive(Debug, Clone, PartialEq, Error)]
pub enum TypesError {
    #[error("Layer with {len} members, more than L_max = {max}")]
    LayerTooLarge { len: usize, max: usize },

    #[error("Empty Layer")]
    EmptyLayer,

    #[error("Invalid probability not in [0,1] : {0}")]
    InvalidProbability(f64),
}
