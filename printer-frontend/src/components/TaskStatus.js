import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Box,
  Grid,
  Chip,
  CircularProgress,
  Alert,
} from '@mui/material';
import axios from 'axios';

const statusColors = {
  pending: 'default',
  scheduled: 'info',
  downloading: 'warning',
  printing: 'warning',
  completed: 'success',
  failed: 'error',
};

function TaskStatus() {
  const { taskId } = useParams();
  const [task, setTask] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchTask = async () => {
      try {
        setLoading(true);
        const response = await axios.get(`http://localhost:8000/tasks/${taskId}`);
        setTask(response.data);
      } catch (err) {
        setError('Failed to fetch task details');
      } finally {
        setLoading(false);
      }
    };

    fetchTask();
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchTask, 5000);
    return () => clearInterval(interval);
  }, [taskId]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="60vh">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Container maxWidth="md" className="container" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  if (!task) {
    return (
      <Container maxWidth="md" className="container" sx={{ mt: 4 }}>
        <Alert severity="info">Task not found</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="md" className="container" sx={{ mt: 4 }}>
      <Paper className="card" elevation={3} sx={{ p: 4 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          Task Details
        </Typography>

        <Grid container spacing={3}>
          <Grid item xs={12}>
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" color="text.secondary">
                Status
              </Typography>
              <Chip
                label={task.status}
                color={statusColors[task.status]}
                sx={{ mt: 1 }}
                className={`status status-${task.status}`}
              />
            </Box>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              File Name
            </Typography>
            <Typography variant="body1" className="list-item">{task.original_filename}</Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Uploader Email
            </Typography>
            <Typography variant="body1" className="list-item">{task.uploader_email}</Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Print Time
            </Typography>
            <Typography variant="body1" className="list-item">
              {new Date(task.time_to_print).toLocaleString()}
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Created At
            </Typography>
            <Typography variant="body1" className="list-item">
              {new Date(task.created_at).toLocaleString()}
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Color Mode
            </Typography>
            <Typography variant="body1" className="list-item" sx={{ textTransform: 'capitalize' }}>
              {task.color_mode}
            </Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Page Size
            </Typography>
            <Typography variant="body1" className="list-item">{task.page_size}</Typography>
          </Grid>

          <Grid item xs={12} sm={6}>
            <Typography variant="subtitle2" color="text.secondary">
              Storage Type
            </Typography>
            <Typography variant="body1" className="list-item" sx={{ textTransform: 'capitalize' }}>
              {task.storage_type}
            </Typography>
          </Grid>

          {task.error_message && (
            <Grid item xs={12}>
              <Alert severity="error" sx={{ mt: 2 }} className="status status-error">
                Error: {task.error_message}
              </Alert>
            </Grid>
          )}
        </Grid>
      </Paper>
    </Container>
  );
}

export default TaskStatus; 