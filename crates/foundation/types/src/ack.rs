use crate::file_descriptor::FileDescriptorId;

struct Ack{
    file_id : FileDescriptorId,
    index : u64,
}