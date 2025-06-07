import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Paper,
  Typography,
  Button,
  Box,
  Card,
  CardContent,
  CardActions,
} from '@mui/material';
import PrintIcon from '@mui/icons-material/Print';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import ListAltIcon from '@mui/icons-material/ListAlt';
import axios from 'axios';

function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    total: 0,
    completed: 0,
    pending: 0,
    failed: 0,
  });

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await axios.get('http://localhost:8000/tasks/');
        const tasks = response.data;
        
        setStats({
          total: tasks.length,
          completed: tasks.filter(t => t.status === 'completed').length,
          pending: tasks.filter(t => ['pending', 'scheduled', 'downloading', 'printing'].includes(t.status)).length,
          failed: tasks.filter(t => t.status === 'failed').length,
        });
      } catch (error) {
        console.error('Failed to fetch stats:', error);
      }
    };

    fetchStats();
  }, []);

  const StatCard = ({ title, value, color }) => (
    <Card className="card" sx={{ height: '100%' }}>
      <CardContent>
        <Typography color="text.secondary" gutterBottom>
          {title}
        </Typography>
        <Typography variant="h4" component="div" color={color}>
          {value}
        </Typography>
      </CardContent>
    </Card>
  );

  return (
    <Container maxWidth="lg" className="container" sx={{ mt: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom sx={{ mb: 4 }}>
        IoT Printer Dashboard
      </Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Total Tasks" value={stats.total} color="primary" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Completed" value={stats.completed} color="success.main" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Pending" value={stats.pending} color="warning.main" />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard title="Failed" value={stats.failed} color="error.main" />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper className="card" sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Upload New Print Task
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Upload a document and schedule it for printing. Support for both local and Google Drive storage.
            </Typography>
            <Button
              variant="contained"
              startIcon={<UploadFileIcon />}
              onClick={() => navigate('/upload')}
              fullWidth
              className="btn btn-primary"
            >
              Upload Document
            </Button>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper className="card" sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              View Print Tasks
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Monitor all your print tasks, their status, and detailed information.
            </Typography>
            <Button
              variant="contained"
              startIcon={<ListAltIcon />}
              onClick={() => navigate('/tasks')}
              fullWidth
              className="btn btn-primary"
            >
              View Tasks
            </Button>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper className="card" sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Quick Print
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Print a document immediately without scheduling.
            </Typography>
            <Button
              variant="contained"
              startIcon={<PrintIcon />}
              onClick={() => navigate('/upload')}
              fullWidth
              className="btn btn-primary"
            >
              Quick Print
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
}

export default Dashboard; 