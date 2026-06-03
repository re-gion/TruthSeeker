-- Expand task input_type from legacy mixed to 15 canonical modality combinations.
alter table public.tasks drop constraint if exists tasks_input_type_check;

update public.tasks
set input_type = 'text_image'
where input_type = 'mixed';

alter table public.tasks add constraint tasks_input_type_check
  check (
    input_type in (
      'text',
      'image',
      'audio',
      'video',
      'text_image',
      'text_audio',
      'text_video',
      'image_audio',
      'image_video',
      'audio_video',
      'text_image_audio',
      'text_image_video',
      'text_audio_video',
      'image_audio_video',
      'text_image_audio_video'
    )
  );
