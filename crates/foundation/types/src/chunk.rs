use crate::file_descriptor::FileDescriptorId;

pub struct Chunk {
    file_id : FileDescriptorId,
    index : u64,
    data : Vec<u8>,
}