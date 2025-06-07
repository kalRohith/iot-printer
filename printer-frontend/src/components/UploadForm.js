import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Alert,
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import axios from 'axios';

function UploadForm() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [uploaderEmail, setUploaderEmail] = useState('');
  const [colorMode, setColorMode] = useState('bw');
  const [pageSize, setPageSize] = useState('A4');
  const [printTime, setPrintTime] = useState(new Date());
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('time_to_print_ts', Math.floor(printTime.getTime() / 1000));
    formData.append('color_mode', colorMode);
    formData.append('page_size', pageSize);
    formData.append('uploader_email', uploaderEmail);

    try {
      const response = await axios.post('http://localhost:8000/add-task/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      navigate(`/tasks/${response.data.task_id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'An error occurred while uploading the file');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" className="container" sx={{ mt: 4 }}>
      <Paper className="card" elevation={3} sx={{ p: 4 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          Upload Print Task
        </Typography>
        
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box component="form" onSubmit={handleSubmit} noValidate className="form-group">
          <Button
            variant="outlined"
            component="label"
            startIcon={<CloudUploadIcon />}
            fullWidth
            sx={{ mb: 2 }}
            className="btn"
          >
            {file ? file.name : 'Choose File'}
            <input
              type="file"
              hidden
              onChange={(e) => setFile(e.target.files[0])}
              required
            />
          </Button>

          <TextField
            margin="normal"
            required
            fullWidth
            label="Email Address"
            type="email"
            value={uploaderEmail}
            onChange={(e) => setUploaderEmail(e.target.value)}
            className="form-control"
          />

          <DateTimePicker
            label="Print Time"
            value={printTime}
            onChange={setPrintTime}
            renderInput={(params) => (
              <TextField {...params} fullWidth margin="normal" required className="form-control" />
            )}
            minDateTime={new Date()}
          />

          <FormControl fullWidth margin="normal" className="form-group">
            <InputLabel>Color Mode</InputLabel>
            <Select
              value={colorMode}
              label="Color Mode"
              onChange={(e) => setColorMode(e.target.value)}
              className="form-control"
            >
              <MenuItem value="color">Color</MenuItem>
              <MenuItem value="bw">Black & White</MenuItem>
            </Select>
          </FormControl>

          <FormControl fullWidth margin="normal" className="form-group">
            <InputLabel>Page Size</InputLabel>
            <Select
              value={pageSize}
              label="Page Size"
              onChange={(e) => setPageSize(e.target.value)}
              className="form-control"
            >
              <MenuItem value="A4">A4</MenuItem>
              <MenuItem value="Letter">Letter</MenuItem>
              <MenuItem value="Legal">Legal</MenuItem>
            </Select>
          </FormControl>

          <Button
            type="submit"
            fullWidth
            variant="contained"
            sx={{ mt: 3 }}
            disabled={loading || !file}
            className="btn btn-primary"
          >
            {loading ? 'Uploading...' : 'Schedule Print Task'}
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default UploadForm; 