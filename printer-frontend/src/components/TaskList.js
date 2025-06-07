import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Box,
  Pagination,
} from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import axios from 'axios';

const statusColors = {
  pending: 'default',
  scheduled: 'info',
  downloading: 'warning',
  printing: 'warning',
  completed: 'success',
  failed: 'error',
};

function TaskList() {
  const navigate = useNavigate();
  const [tasks, setTasks] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchTasks = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`http://localhost:8000/tasks/?skip=${(page - 1) * 10}&limit=10`);
      setTasks(response.data);
      setTotalPages(Math.ceil(response.data.length / 10));
    } catch (err) {
      setError('Failed to fetch tasks');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [page]);

  const handlePageChange = (event, value) => {
    setPage(value);
  };

  return (
    <Container maxWidth="lg" className="container" sx={{ mt: 4 }}>
      <Paper className="card" elevation={3} sx={{ p: 3 }}>
        <Typography variant="h5" component="h1" gutterBottom>
          Print Tasks
        </Typography>

        <TableContainer>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>ID</TableCell>
                <TableCell>Filename</TableCell>
                <TableCell>Email</TableCell>
                <TableCell>Print Time</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tasks.map((task) => (
                <TableRow key={task.id} className="list-item">
                  <TableCell>{task.id}</TableCell>
                  <TableCell>{task.original_filename}</TableCell>
                  <TableCell>{task.uploader_email}</TableCell>
                  <TableCell>
                    {new Date(task.time_to_print).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={task.status}
                      color={statusColors[task.status]}
                      size="small"
                      className={`status status-${task.status}`}
                    />
                  </TableCell>
                  <TableCell>
                    <IconButton
                      onClick={() => navigate(`/tasks/${task.id}`)}
                      size="small"
                      className="btn"
                    >
                      <VisibilityIcon />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
          <Pagination
            count={totalPages}
            page={page}
            onChange={handlePageChange}
            color="primary"
            className="btn"
          />
        </Box>
      </Paper>
    </Container>
  );
}

export default TaskList; 